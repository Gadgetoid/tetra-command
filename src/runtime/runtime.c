#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

#define MINICORO_IMPL
#include "minicoro.h"

#include "py/runtime.h"
#include "py/compile.h"
#include "py/lexer.h"
#include "py/gc.h"
#include "py/stackctrl.h"
#include "port/micropython_embed.h"

#if MICROPY_VFS
#include "extmod/vfs.h"
#include "extmod/vfs_posix.h"
#endif

#include "runtime.h"

#ifndef MACROPAD_GC_HEAP
#define MACROPAD_GC_HEAP (24 * 1024 * 1024)
#endif
#ifndef MACROPAD_PY_STACK
#define MACROPAD_PY_STACK (1024 * 1024)
#endif

static mco_coro *fiber = NULL;
static char *gc_heap = NULL;
static char *app_source = NULL;
static const macropad_config_t *config = NULL;
static char root_abs[PATH_MAX];
static char data_abs[PATH_MAX];

void host_yield_to_main(void) { mco_yield(mco_running()); }

static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) return NULL;
    fseek(f, 0, SEEK_END);
    long n = ftell(f);
    fseek(f, 0, SEEK_SET);
    char *buf = malloc(n + 1);
    if (!buf) { fclose(f); return NULL; }
    if (fread(buf, 1, n, f) != (size_t)n) { free(buf); fclose(f); return NULL; }
    buf[n] = '\0';
    fclose(f);
    return buf;
}

#if MICROPY_VFS
static mp_vfs_mount_t *new_mount(const char *point, const char *dir) {
    mp_obj_t args[] = { mp_obj_new_str(dir, strlen(dir)) };
    mp_obj_t vfs = mp_call_function_n_kw(MP_OBJ_FROM_PTR(&mp_type_vfs_posix), 1, 0, args);

    mp_vfs_mount_t *mount = m_new_obj(mp_vfs_mount_t);
    mount->str = point;
    mount->len = strlen(point);
    mount->obj = vfs;
    mount->next = NULL;
    return mount;
}

// The app directory as /, the writable one as /data. mp_vfs_lookup_path walks
// the table in order and / matches everything, so / has to be last.
static void mount_filesystems(const char *root, const char *data) {
    mp_vfs_mount_t *mount = new_mount("/data", data);
    mount->next = new_mount("/", root);

    MP_STATE_VM(vfs_mount_table) = mount;
    MP_STATE_VM(vfs_cur) = mount->next;

    // Without this the VFS cwd stays empty, so relative paths and the ""
    // entry in sys.path (which is how `import` finds local modules) fail.
    mp_vfs_chdir(mp_obj_new_str("/", 1));
}
#endif

// Not mp_embed_exec_str(): that compiles with is_repl=true, which makes
// MicroPython echo the value of every expression statement to stdout.
static void py_exec(const char *src, const char *name) {
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) {
        mp_lexer_t *lex = mp_lexer_new_from_str_len(qstr_from_str(name), src, strlen(src), 0);
        qstr source_name = lex->source_name;
        mp_parse_tree_t parse_tree = mp_parse(lex, MP_PARSE_FILE_INPUT);
        mp_obj_t module_fun = mp_compile(&parse_tree, source_name, false);
        mp_call_function_0(module_fun);
        nlr_pop();
    } else {
        mp_obj_print_exception(&mp_plat_print, (mp_obj_t)nlr.ret_val);
    }
}

static void fiber_entry(mco_coro *co) {
    (void)co;
    int stack_marker;   // fiber's own stack; GC scanning and NLR key off this
    mp_embed_init(gc_heap, MACROPAD_GC_HEAP, &stack_marker);

    // mp_embed_init sets the stack top but never a limit. With MICROPY_STACK_CHECK
    // on (the default at EXTRA_FEATURES) an unset limit trips every check, and the
    // failure is silent because even printing an exception needs the stack. Size it
    // to the fiber's own stack, leaving headroom for the C frames underneath.
    mp_stack_set_limit(MACROPAD_PY_STACK - 64 * 1024);

    #if MICROPY_VFS
    nlr_buf_t nlr;
    if (nlr_push(&nlr) == 0) {
        mount_filesystems(root_abs, data_abs);
        mp_obj_list_append(mp_sys_path, MP_OBJ_NEW_QSTR(MP_QSTR__slash_));
        nlr_pop();
    } else {
        mp_obj_print_exception(&mp_plat_print, (mp_obj_t)nlr.ret_val);
    }
    #endif

    py_exec(app_source, config->app_path);
    mp_embed_deinit();
}

bool runtime_init(const macropad_config_t *cfg) {
    config = cfg;

    // Resolve both once so the mounts do not depend on the process cwd.
    if (!realpath(cfg->root_path, root_abs)) {
        fprintf(stderr, "tetra-command: cannot resolve root %s\n", cfg->root_path);
        return false;
    }
    if (!realpath(cfg->data_path, data_abs)) {
        fprintf(stderr, "tetra-command: cannot resolve data dir %s\n", cfg->data_path);
        return false;
    }

    char path[PATH_MAX * 2];
    snprintf(path, sizeof(path), "%s/%s", root_abs, cfg->app_path);
    app_source = read_file(path);
    if (!app_source) {
        fprintf(stderr, "tetra-command: cannot read %s\n", path);
        return false;
    }

    gc_heap = malloc(MACROPAD_GC_HEAP);
    if (!gc_heap) return false;

    mco_desc desc = mco_desc_init(fiber_entry, MACROPAD_PY_STACK);
    return mco_create(&fiber, &desc) == MCO_SUCCESS;
}

bool runtime_step(void) {
    if (!fiber || mco_status(fiber) == MCO_DEAD) return false;
    return mco_resume(fiber) == MCO_SUCCESS;
}

bool runtime_finished(void) {
    return !fiber || mco_status(fiber) == MCO_DEAD;
}

void runtime_deinit(void) {
    if (fiber) { mco_destroy(fiber); fiber = NULL; }
    free(gc_heap); gc_heap = NULL;
    free(app_source); app_source = NULL;
}
