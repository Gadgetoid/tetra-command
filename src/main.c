#include <SDL3/SDL.h>
#include <limits.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "host.h"
#include "children.h"
#include "location.h"
#include "paths.h"
#include "display/display.h"
#include "display/ddc.h"
#include "input/input.h"
#include "runtime/runtime.h"
#include "py/runtime.h"

static volatile sig_atomic_t interrupt_flag = 0;
static bool quit_flag = false;
static uint64_t start_ticks = 0;

uint32_t host_ticks_ms(void)   { return (uint32_t)(SDL_GetTicks() - start_ticks); }
bool     host_quit_requested(void) { return quit_flag; }
void     host_request_quit(void)   { quit_flag = true; }

// Runs on the Python fiber every MICROPY_VM_HOOK_COUNT bytecodes. This is the
// escape hatch for a `while True:` that never calls host.present().
void host_vm_hook(void) {
    if (interrupt_flag) {
        interrupt_flag = 0;
        quit_flag = true;
        mp_sched_keyboard_interrupt();
    }
}

// No REPL or stdin here; interrupts arrive via SIGINT and the VM hook.
void mp_hal_set_interrupt_char(int c) { (void)c; }

static void on_sigint(int sig) { (void)sig; interrupt_flag = 1; }

static void usage(void) {
    printf(
        "usage: tetra-command [options]\n"
        "  --display=NAME   substring of the display name (default TETRA)\n"
        "  --root=DIR       directory mounted as / (default the bundle, else ./py)\n"
        "  --data=DIR       directory mounted as /data, written by the app\n"
        "  --app=FILE       entry point within root (default app.py)\n"
        "  --size=WxH       override render size\n"
        "  --windowed       do not go fullscreen\n"
        "  --no-tools       do not run the sampler and weather fetch as children\n"
        "  --list-displays  print displays and exit\n");
}

// Everything the app ships with. Contents/Resources in a bundle, the working
// directory otherwise.
static void app_tree(char *out, size_t len) {
    if (!paths_resources(out, len)) snprintf(out, len, ".");
}

// The interpreter travels with the app: a Finder launch has almost no PATH.
static void tools_python(char *out, size_t len, const char *tree) {
    snprintf(out, len, "%s/venv/bin/python3", tree);
    if (access(out, X_OK) == 0) return;
    snprintf(out, len, "%s/.venv/bin/python3", tree);   // what `uv sync` makes
}

int main(int argc, char **argv) {
    macropad_config_t cfg = {
        .display_name = "TETRA",
        .app_path     = "app.py",
        .root_path    = NULL,       // filled in from the app tree below
        .data_path    = NULL,       // filled in from the data directory below
        .width = 0, .height = 0,
        .windowed = false,
        .list_displays = false,
    };
    bool tools = true;

    for (int i = 1; i < argc; i++) {
        const char *a = argv[i];
        if      (!strncmp(a, "--display=", 10)) cfg.display_name = a + 10;
        else if (!strncmp(a, "--root=", 7))     cfg.root_path = a + 7;
        else if (!strncmp(a, "--data=", 7))     cfg.data_path = a + 7;
        else if (!strncmp(a, "--app=", 6))      cfg.app_path = a + 6;
        else if (!strncmp(a, "--size=", 7))     sscanf(a + 7, "%dx%d", &cfg.width, &cfg.height);
        else if (!strcmp(a, "--windowed"))      cfg.windowed = true;
        else if (!strcmp(a, "--no-tools"))      tools = false;
        else if (!strcmp(a, "--list-displays")) cfg.list_displays = true;
        else { usage(); return a[0] == '-' && !strcmp(a, "--help") ? 0 : 1; }
    }

    char tree[PATH_MAX], root[PATH_MAX], data[PATH_MAX];
    app_tree(tree, sizeof tree);
    if (!cfg.root_path) {
        snprintf(root, sizeof root, "%s/py", tree);
        cfg.root_path = root;
    }
    if (!cfg.data_path) {
        if (!paths_data(data, sizeof data)) {
            fprintf(stderr, "tetra-command: no writable data directory\n");
            return 1;
        }
        cfg.data_path = data;
    }

    if (cfg.list_displays) {
        if (!SDL_Init(SDL_INIT_VIDEO)) return 1;
        display_list();
        SDL_Quit();
        return 0;
    }

    setvbuf(stdout, NULL, _IONBF, 0);   // keep Python output ahead of any crash
    signal(SIGINT, on_sigint);
    start_ticks = SDL_GetTicks();

    input_queue_init();
    if (!display_init(&cfg)) return 1;
    input_init_all(host_width, host_height);
    ddc_init(&cfg);

    if (!runtime_init(&cfg)) { display_deinit(); return 1; }

    location_start(cfg.data_path);

    if (tools) {
        char python[PATH_MAX], script[PATH_MAX];
        tools_python(python, sizeof python, tree);

        const char *sampler[] = { "--data", cfg.data_path, "--watch",
                                  "--exit-with-parent", NULL };
        snprintf(script, sizeof script, "%s/tools/fetch_stats.py", tree);
        child_spawn(python, script, sampler);

        const char *weather[] = { "--data", cfg.data_path, "--auto", "--watch",
                                  "--exit-with-parent", NULL };
        snprintf(script, sizeof script, "%s/tools/fetch_weather.py", tree);
        child_spawn(python, script, weather);
    }

    uint64_t frames = 0, t0 = SDL_GetTicks();
    while (!quit_flag) {
        if (!display_pump_events()) break;
        if (!runtime_step()) break;
        if (runtime_finished()) break;
        display_present_frame();
        frames++;
    }

    uint64_t dt = SDL_GetTicks() - t0;
    SDL_Log("%llu frames in %llu ms (%.1f fps)",
            (unsigned long long)frames, (unsigned long long)dt,
            dt ? frames * 1000.0 / dt : 0.0);

    children_stop();
    location_stop();
    runtime_deinit();
    ddc_deinit();
    input_deinit_all();
    display_deinit();
    input_queue_deinit();
    return 0;
}
