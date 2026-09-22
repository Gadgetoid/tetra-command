// Expose the panel's OSD controls to Python.
//
//   ddc.available()          -> True when the panel answered DDC/CI at startup
//   ddc.get(ddc.BRIGHTNESS)  -> (current, maximum), or None if unsupported
//   ddc.set(ddc.BRIGHTNESS, 75)
//
// set() returns immediately; see ddc.h for how writes are coalesced. get() can
// block on its first call for a given code, so read what you need once at
// startup rather than inside a drag.

#include "py/runtime.h"
#include "py/objtuple.h"

#include "display/ddc.h"

static mp_obj_t mod_ddc_available(void) {
    return mp_obj_new_bool(ddc_available());
}
static MP_DEFINE_CONST_FUN_OBJ_0(mod_ddc_available_obj, mod_ddc_available);

static mp_obj_t mod_ddc_get(mp_obj_t code_in) {
    mp_int_t code = mp_obj_get_int(code_in);
    if (code < 0 || code > 0xff) mp_raise_ValueError(MP_ERROR_TEXT("VCP code out of range"));

    int current = 0, maximum = 0;
    if (!ddc_get((uint8_t)code, &current, &maximum)) return mp_const_none;

    mp_obj_t t[2] = { MP_OBJ_NEW_SMALL_INT(current), MP_OBJ_NEW_SMALL_INT(maximum) };
    return mp_obj_new_tuple(2, t);
}
static MP_DEFINE_CONST_FUN_OBJ_1(mod_ddc_get_obj, mod_ddc_get);

static mp_obj_t mod_ddc_set(mp_obj_t code_in, mp_obj_t value_in) {
    mp_int_t code = mp_obj_get_int(code_in);
    if (code < 0 || code > 0xff) mp_raise_ValueError(MP_ERROR_TEXT("VCP code out of range"));

    ddc_set((uint8_t)code, mp_obj_get_int(value_in));
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_2(mod_ddc_set_obj, mod_ddc_set);

static const mp_rom_map_elem_t ddc_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),      MP_ROM_QSTR(MP_QSTR_ddc) },
    { MP_ROM_QSTR(MP_QSTR_available),     MP_ROM_PTR(&mod_ddc_available_obj) },
    { MP_ROM_QSTR(MP_QSTR_get),           MP_ROM_PTR(&mod_ddc_get_obj) },
    { MP_ROM_QSTR(MP_QSTR_set),           MP_ROM_PTR(&mod_ddc_set_obj) },
    { MP_ROM_QSTR(MP_QSTR_BRIGHTNESS),    MP_ROM_INT(DDC_BRIGHTNESS) },
    { MP_ROM_QSTR(MP_QSTR_CONTRAST),      MP_ROM_INT(DDC_CONTRAST) },
    { MP_ROM_QSTR(MP_QSTR_COLOUR_PRESET), MP_ROM_INT(DDC_COLOUR_PRESET) },
    { MP_ROM_QSTR(MP_QSTR_GAIN_RED),      MP_ROM_INT(DDC_GAIN_RED) },
    { MP_ROM_QSTR(MP_QSTR_GAIN_GREEN),    MP_ROM_INT(DDC_GAIN_GREEN) },
    { MP_ROM_QSTR(MP_QSTR_GAIN_BLUE),     MP_ROM_INT(DDC_GAIN_BLUE) },
    { MP_ROM_QSTR(MP_QSTR_INPUT_SOURCE),  MP_ROM_INT(DDC_INPUT_SOURCE) },
    { MP_ROM_QSTR(MP_QSTR_BLACK_RED),     MP_ROM_INT(DDC_BLACK_RED) },
    { MP_ROM_QSTR(MP_QSTR_BLACK_GREEN),   MP_ROM_INT(DDC_BLACK_GREEN) },
    { MP_ROM_QSTR(MP_QSTR_BLACK_BLUE),    MP_ROM_INT(DDC_BLACK_BLUE) },
    { MP_ROM_QSTR(MP_QSTR_POWER_MODE),    MP_ROM_INT(DDC_POWER_MODE) },
};
static MP_DEFINE_CONST_DICT(ddc_module_globals, ddc_module_globals_table);

const mp_obj_module_t ddc_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&ddc_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_ddc, ddc_module);
