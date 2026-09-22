#include <SDL3/SDL.h>
#include <stdlib.h>
#include <string.h>

#include "display.h"
#include "window.h"
#include "input/input.h"

uint32_t *host_framebuffer = NULL;
int host_width = 0, host_height = 0;

static SDL_Window   *window = NULL;
static SDL_Renderer *renderer = NULL;
static SDL_Texture  *texture = NULL;
static bool quit_flag = false;

void display_list(void) {
    int n = 0;
    SDL_DisplayID *ids = SDL_GetDisplays(&n);
    SDL_Log("%d display(s):", n);
    for (int i = 0; i < n; i++) {
        SDL_Rect r;
        SDL_GetDisplayBounds(ids[i], &r);
        SDL_Log("  [%u] %-28s %dx%d at %d,%d",
                ids[i], SDL_GetDisplayName(ids[i]), r.w, r.h, r.x, r.y);
    }
    SDL_free(ids);
}

static SDL_DisplayID pick_display(const char *want) {
    int n = 0;
    SDL_DisplayID *ids = SDL_GetDisplays(&n);
    SDL_DisplayID chosen = (ids && n) ? ids[0] : 0;
    if (want && *want) {
        for (int i = 0; i < n; i++) {
            const char *name = SDL_GetDisplayName(ids[i]);
            if (name && strstr(name, want)) { chosen = ids[i]; break; }
        }
    }
    SDL_free(ids);
    return chosen;
}

bool display_init(const macropad_config_t *cfg) {
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        SDL_Log("SDL_Init failed: %s", SDL_GetError());
        return false;
    }

    SDL_DisplayID target = pick_display(cfg->display_name);
    SDL_Rect bounds;
    SDL_GetDisplayBounds(target, &bounds);

    host_width  = cfg->width  > 0 ? cfg->width  : bounds.w;
    host_height = cfg->height > 0 ? cfg->height : bounds.h;
    SDL_Log("display: [%u] %s, rendering %dx%d",
            target, SDL_GetDisplayName(target), host_width, host_height);

    window = SDL_CreateWindow("macropad", host_width, host_height, SDL_WINDOW_BORDERLESS);
    if (!window) { SDL_Log("SDL_CreateWindow failed: %s", SDL_GetError()); return false; }
    SDL_SetWindowPosition(window, bounds.x, bounds.y);

    // Not SDL fullscreen: it sets the app-wide presentation options, and the
    // Dock then follows focus onto this display and hides under us.
    if (!cfg->windowed) {
        void *native = SDL_GetPointerProperty(SDL_GetWindowProperties(window),
                                              SDL_PROP_WINDOW_COCOA_WINDOW_POINTER,
                                              NULL);
        if (!window_raise_above_menu_bar(native)) {
            SDL_Log("display: could not raise over the menu bar, it may overlap");
        }
    }
    SDL_RaiseWindow(window);

    renderer = SDL_CreateRenderer(window, NULL);
    if (!renderer) { SDL_Log("SDL_CreateRenderer failed: %s", SDL_GetError()); return false; }

    // RGBA32 is byte order R,G,B,A, which is picovector's RGBA8888 layout.
    texture = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA32,
                                SDL_TEXTUREACCESS_STREAMING, host_width, host_height);
    if (!texture) { SDL_Log("SDL_CreateTexture failed: %s", SDL_GetError()); return false; }
    SDL_SetTextureScaleMode(texture, SDL_SCALEMODE_LINEAR);

    host_framebuffer = calloc((size_t)host_width * host_height, sizeof(uint32_t));
    return host_framebuffer != NULL;
}

void display_present_frame(void) {
    SDL_UpdateTexture(texture, NULL, host_framebuffer, host_width * 4);
    SDL_RenderClear(renderer);

    // Scale up to fill the window but keep the framebuffer's aspect, so a
    // badge-sized 4:3 layout is not stretched across a 16:10 panel.
    int ww = 0, wh = 0;
    SDL_GetCurrentRenderOutputSize(renderer, &ww, &wh);
    float scale = SDL_min((float)ww / host_width, (float)wh / host_height);
    SDL_FRect dst = {
        ((float)ww - host_width * scale) * 0.5f,
        ((float)wh - host_height * scale) * 0.5f,
        host_width * scale, host_height * scale,
    };
    SDL_RenderTexture(renderer, texture, NULL, &dst);
    SDL_RenderPresent(renderer);
}

bool display_pump_events(void) {
    SDL_Event e;
    while (SDL_PollEvent(&e)) {
        switch (e.type) {
            case SDL_EVENT_QUIT:
                quit_flag = true;
                break;
            case SDL_EVENT_KEY_DOWN:
                if (e.key.key == SDLK_ESCAPE) quit_flag = true;
                break;
            // SDL reports no touch device for the Tetra (macOS never routes an
            // external digitizer), so the mouse is the portable fallback driver.
            case SDL_EVENT_MOUSE_BUTTON_DOWN:
                input_push(HOST_EV_DOWN, 0, (uint16_t)e.button.x, (uint16_t)e.button.y);
                break;
            case SDL_EVENT_MOUSE_BUTTON_UP:
                input_push(HOST_EV_UP, 0, (uint16_t)e.button.x, (uint16_t)e.button.y);
                break;
            case SDL_EVENT_MOUSE_MOTION:
                if (e.motion.state & SDL_BUTTON_LMASK)
                    input_push(HOST_EV_MOVE, 0, (uint16_t)e.motion.x, (uint16_t)e.motion.y);
                break;
            default:
                break;
        }
    }
    return !quit_flag;
}

void display_deinit(void) {
    free(host_framebuffer);
    host_framebuffer = NULL;
    if (texture)  SDL_DestroyTexture(texture);
    if (renderer) SDL_DestroyRenderer(renderer);
    if (window)   SDL_DestroyWindow(window);
    SDL_Quit();
}
