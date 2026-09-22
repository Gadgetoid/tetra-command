#include "py/runtime.h"
#include "py/objtuple.h"
#include "py/objarray.h"
#include <time.h>
#include "host.h"
#include "input/input.h"

static mp_obj_t host_size(void) {
    mp_obj_t t[2] = { MP_OBJ_NEW_SMALL_INT(host_width), MP_OBJ_NEW_SMALL_INT(host_height) };
    return mp_obj_new_tuple(2, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_size_obj, host_size);

static mp_obj_t host_present(void) {
    host_yield_to_main();
    if (host_quit_requested()) {
        mp_raise_type(&mp_type_SystemExit);
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_present_obj, host_present);

static mp_obj_t host_ticks(void) {
    return mp_obj_new_int_from_uint(host_ticks_ms());
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_ticks_obj, host_ticks);

static mp_obj_t host_fill(mp_obj_t color_in) {
    uint32_t c = (uint32_t)mp_obj_get_int_truncated(color_in);
    size_t n = (size_t)host_width * host_height;
    for (size_t i = 0; i < n; i++) host_framebuffer[i] = c;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(host_fill_obj, host_fill);

static mp_obj_t host_rect(size_t n_args, const mp_obj_t *args) {
    (void)n_args;
    int x = mp_obj_get_int(args[0]), y = mp_obj_get_int(args[1]);
    int w = mp_obj_get_int(args[2]), h = mp_obj_get_int(args[3]);
    uint32_t c = (uint32_t)mp_obj_get_int_truncated(args[4]);
    int x0 = x < 0 ? 0 : x, y0 = y < 0 ? 0 : y;
    int x1 = x + w > host_width ? host_width : x + w;
    int y1 = y + h > host_height ? host_height : y + h;
    for (int j = y0; j < y1; j++)
        for (int i = x0; i < x1; i++)
            host_framebuffer[(size_t)j * host_width + i] = c;
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_VAR_BETWEEN(host_rect_obj, 5, 5, host_rect);

// A bytearray view over the framebuffer, for picovector.image(w, h, buffer).
// Layout is RGBA8888 in memory order, matching picovector's native format.
static mp_obj_t host_framebuffer_obj_fn(void) {
    return mp_obj_new_bytearray_by_ref((size_t)host_width * host_height * 4, host_framebuffer);
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_framebuffer_obj, host_framebuffer_obj_fn);

// MicroPython's time.localtime() tuple order, off the host clock.
static mp_obj_t host_localtime(void) {
    time_t now = time(NULL);
    struct tm lt;
    localtime_r(&now, &lt);
    mp_obj_t t[8] = {
        MP_OBJ_NEW_SMALL_INT(lt.tm_year + 1900), MP_OBJ_NEW_SMALL_INT(lt.tm_mon + 1),
        MP_OBJ_NEW_SMALL_INT(lt.tm_mday),        MP_OBJ_NEW_SMALL_INT(lt.tm_hour),
        MP_OBJ_NEW_SMALL_INT(lt.tm_min),         MP_OBJ_NEW_SMALL_INT(lt.tm_sec),
        MP_OBJ_NEW_SMALL_INT((lt.tm_wday + 6) % 7), MP_OBJ_NEW_SMALL_INT(lt.tm_yday + 1),
    };
    return mp_obj_new_tuple(8, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_localtime_obj, host_localtime);

// Seconds since the epoch; ticks_ms restarts every launch. Not
// mp_obj_new_int_from_ll, which always raises under MICROPY_LONGINT_IMPL_NONE.
static mp_obj_t host_epoch(void) {
    return mp_obj_new_int((mp_int_t)time(NULL));
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_epoch_obj, host_epoch);

static mp_obj_t host_poll(void) {
    host_event_t ev;
    if (!input_pop(&ev)) return mp_const_none;
    mp_obj_t t[4] = {
        MP_OBJ_NEW_SMALL_INT(ev.kind), MP_OBJ_NEW_SMALL_INT(ev.finger),
        MP_OBJ_NEW_SMALL_INT(ev.x),    MP_OBJ_NEW_SMALL_INT(ev.y),
    };
    return mp_obj_new_tuple(4, t);
}
static MP_DEFINE_CONST_FUN_OBJ_0(host_poll_obj, host_poll);

static const mp_rom_map_elem_t host_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__), MP_ROM_QSTR(MP_QSTR_host) },
    { MP_ROM_QSTR(MP_QSTR_size),     MP_ROM_PTR(&host_size_obj) },
    { MP_ROM_QSTR(MP_QSTR_present),  MP_ROM_PTR(&host_present_obj) },
    { MP_ROM_QSTR(MP_QSTR_ticks_ms), MP_ROM_PTR(&host_ticks_obj) },
    { MP_ROM_QSTR(MP_QSTR_fill),     MP_ROM_PTR(&host_fill_obj) },
    { MP_ROM_QSTR(MP_QSTR_rect),     MP_ROM_PTR(&host_rect_obj) },
    { MP_ROM_QSTR(MP_QSTR_poll),     MP_ROM_PTR(&host_poll_obj) },
    { MP_ROM_QSTR(MP_QSTR_framebuffer), MP_ROM_PTR(&host_framebuffer_obj) },
    { MP_ROM_QSTR(MP_QSTR_localtime),   MP_ROM_PTR(&host_localtime_obj) },
    { MP_ROM_QSTR(MP_QSTR_epoch),       MP_ROM_PTR(&host_epoch_obj) },
    { MP_ROM_QSTR(MP_QSTR_DOWN),     MP_ROM_INT(HOST_EV_DOWN) },
    { MP_ROM_QSTR(MP_QSTR_MOVE),     MP_ROM_INT(HOST_EV_MOVE) },
    { MP_ROM_QSTR(MP_QSTR_UP),       MP_ROM_INT(HOST_EV_UP) },
};
static MP_DEFINE_CONST_DICT(host_module_globals, host_module_globals_table);

const mp_obj_module_t host_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&host_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_host, host_module);
