// Pretend to be a HID keyboard, on macOS.
//
// The API matches the ISOXLIIS firmware's: you hand over the set of HID usages
// held *right now*, and the transitions are worked out here. A macro is then a
// generator yielding "what is held this step", exactly as it is on the badge,
// and the same macro source runs in both places.
//
// macOS has no way to publish a virtual HID device without a signed driver, so
// the held set is replayed as CGEvents instead. That needs Accessibility
// permission for whichever app owns this process - the bundle when launched
// from Finder, the terminal when launched from one: hid.ready() reports
// whether it has been granted, and asks for it if not.

#include <ApplicationServices/ApplicationServices.h>

#include "py/runtime.h"
#include "py/objarray.h"

#define HID_USAGE_MAX 256

// HID usage -> macOS virtual keycode, ANSI layout. -1 where there is no key.
static const int16_t HID_TO_VK[HID_USAGE_MAX] = {
    [0x04] = 0,  [0x05] = 11, [0x06] = 8,  [0x07] = 2,  [0x08] = 14, [0x09] = 3,
    [0x0a] = 5,  [0x0b] = 4,  [0x0c] = 34, [0x0d] = 38, [0x0e] = 40, [0x0f] = 37,
    [0x10] = 46, [0x11] = 45, [0x12] = 31, [0x13] = 35, [0x14] = 12, [0x15] = 15,
    [0x16] = 1,  [0x17] = 17, [0x18] = 32, [0x19] = 9,  [0x1a] = 13, [0x1b] = 7,
    [0x1c] = 16, [0x1d] = 6,
    [0x1e] = 18, [0x1f] = 19, [0x20] = 20, [0x21] = 21, [0x22] = 23, [0x23] = 22,
    [0x24] = 26, [0x25] = 28, [0x26] = 25, [0x27] = 29,
    [0x28] = 36, [0x29] = 53, [0x2a] = 51, [0x2b] = 48, [0x2c] = 49,
    [0x2d] = 27, [0x2e] = 24, [0x2f] = 33, [0x30] = 30, [0x31] = 42,
    [0x33] = 41, [0x34] = 39, [0x35] = 50, [0x36] = 43, [0x37] = 47, [0x38] = 44,
    [0x39] = 57,
    [0x3a] = 122, [0x3b] = 120, [0x3c] = 99,  [0x3d] = 118, [0x3e] = 96,
    [0x3f] = 97,  [0x40] = 98,  [0x41] = 100, [0x42] = 101, [0x43] = 109,
    [0x44] = 103, [0x45] = 111,
    [0x49] = 114, [0x4a] = 115, [0x4b] = 116, [0x4c] = 117, [0x4d] = 119,
    [0x4e] = 121, [0x4f] = 124, [0x50] = 123, [0x51] = 125, [0x52] = 126,
    // Modifiers.
    [0xe0] = 59, [0xe1] = 56, [0xe2] = 58, [0xe3] = 55,
    [0xe4] = 62, [0xe5] = 60, [0xe6] = 61, [0xe7] = 54,
};

static bool held[HID_USAGE_MAX];
static CGEventSourceRef event_source = NULL;

static CGEventFlags flags_for_held(void) {
    CGEventFlags flags = 0;
    if (held[0xe0] || held[0xe4]) flags |= kCGEventFlagMaskControl;
    if (held[0xe1] || held[0xe5]) flags |= kCGEventFlagMaskShift;
    if (held[0xe2] || held[0xe6]) flags |= kCGEventFlagMaskAlternate;
    if (held[0xe3] || held[0xe7]) flags |= kCGEventFlagMaskCommand;
    return flags;
}

// Real arrow and navigation events carry bits a synthesised one does not get
// for free, and some system handlers test them: Mission Control's ctrl-Up sees
// nothing without the numeric-pad bit, while cmd-shift-4 never needed it.
static CGEventFlags flags_for_key(uint8_t usage) {
    if (usage >= 0x4f && usage <= 0x52) {   // arrows
        return kCGEventFlagMaskNumericPad | kCGEventFlagMaskSecondaryFn;
    }
    if ((usage >= 0x3a && usage <= 0x45) || // F1-F12
        (usage >= 0x49 && usage <= 0x4e)) { // insert/home/pgup/del/end/pgdn
        return kCGEventFlagMaskSecondaryFn;
    }
    return 0;
}

static void post(uint8_t usage, bool down) {
    int16_t vk = HID_TO_VK[usage];
    if (vk < 0 || (vk == 0 && usage != 0x04)) return;   // 0 is 'A'; everything else unmapped
    CGEventRef e = CGEventCreateKeyboardEvent(event_source, (CGKeyCode)vk, down);
    if (!e) return;
    // Apps read modifiers off the event's flags, not off the key history, so
    // every event carries the state as it is *after* this transition.
    CGEventSetFlags(e, flags_for_held() | flags_for_key(usage));
    CGEventPost(kCGHIDEventTap, e);
    CFRelease(e);
}

// hid.ready() -> True once Accessibility is granted to the owning app.
//
// Asks when it has not been. Launched from Finder there is nowhere for a
// printed hint to go, so without the system prompt the macro pad is simply
// dead with no way to find out why.
static mp_obj_t hid_ready(void) {
    if (AXIsProcessTrusted()) return mp_obj_new_bool(true);

    const void *keys[] = { kAXTrustedCheckOptionPrompt };
    const void *values[] = { kCFBooleanTrue };
    CFDictionaryRef options = CFDictionaryCreate(
        NULL, keys, values, 1,
        &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    bool trusted = AXIsProcessTrustedWithOptions(options);
    CFRelease(options);
    return mp_obj_new_bool(trusted);
}
static MP_DEFINE_CONST_FUN_OBJ_0(hid_ready_obj, hid_ready);

// hid.send_keys(usages) -- the complete set held now; transitions are derived.
static mp_obj_t hid_send_keys(mp_obj_t keys_in) {
    bool want[HID_USAGE_MAX] = { false };

    mp_obj_iter_buf_t buf;
    mp_obj_t iterable = mp_getiter(keys_in, &buf);
    mp_obj_t item;
    while ((item = mp_iternext(iterable)) != MP_OBJ_STOP_ITERATION) {
        mp_int_t usage = mp_obj_get_int(item);
        if (usage > 0 && usage < HID_USAGE_MAX) want[usage] = true;
    }

    if (event_source == NULL) {
        event_source = CGEventSourceCreate(kCGEventSourceStateHIDSystemState);
    }

    // Modifiers first on the way down and last on the way up, so a chord never
    // lands as a bare keypress in the window that is about to receive it.
    for (int u = 0xe0; u <= 0xe7; u++) {
        if (want[u] && !held[u]) { held[u] = true; post((uint8_t)u, true); }
    }
    for (int u = 1; u < 0xe0; u++) {
        if (want[u] && !held[u]) { held[u] = true; post((uint8_t)u, true); }
    }
    for (int u = 1; u < 0xe0; u++) {
        if (!want[u] && held[u]) { held[u] = false; post((uint8_t)u, false); }
    }
    for (int u = 0xe0; u <= 0xe7; u++) {
        if (!want[u] && held[u]) { held[u] = false; post((uint8_t)u, false); }
    }
    return mp_const_none;
}
static MP_DEFINE_CONST_FUN_OBJ_1(hid_send_keys_obj, hid_send_keys);

// hid.release_all() -- drop anything still held, e.g. when a macro is cancelled.
static mp_obj_t hid_release_all(void) {
    mp_obj_t empty = mp_obj_new_list(0, NULL);
    return hid_send_keys(empty);
}
static MP_DEFINE_CONST_FUN_OBJ_0(hid_release_all_obj, hid_release_all);

static const mp_rom_map_elem_t hid_module_globals_table[] = {
    { MP_ROM_QSTR(MP_QSTR___name__),    MP_ROM_QSTR(MP_QSTR_hid) },
    { MP_ROM_QSTR(MP_QSTR_ready),       MP_ROM_PTR(&hid_ready_obj) },
    { MP_ROM_QSTR(MP_QSTR_send_keys),   MP_ROM_PTR(&hid_send_keys_obj) },
    { MP_ROM_QSTR(MP_QSTR_release_all), MP_ROM_PTR(&hid_release_all_obj) },
};
static MP_DEFINE_CONST_DICT(hid_module_globals, hid_module_globals_table);

const mp_obj_module_t hid_module = {
    .base = { &mp_type_module },
    .globals = (mp_obj_dict_t *)&hid_module_globals,
};

MP_REGISTER_MODULE(MP_QSTR_hid, hid_module);
