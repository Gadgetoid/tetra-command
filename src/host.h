// Shared host <-> driver <-> runtime interface.
#pragma once
#include <stdbool.h>
#include <stdint.h>

#define HOST_EV_DOWN 1
#define HOST_EV_MOVE 2
#define HOST_EV_UP   3

typedef struct {
    uint8_t  kind;
    uint8_t  finger;
    uint16_t x, y;
} host_event_t;

// Runtime configuration, all settable from the command line.
typedef struct {
    const char *display_name;   // substring match against the OS display name
    const char *app_path;       // python entry point, relative to root
    const char *root_path;      // directory mounted as / inside MicroPython
    const char *data_path;      // directory mounted as /data, the writable one
    int         width, height;  // 0 = take from the display
    bool        windowed;
    bool        list_displays;
} macropad_config_t;

// The framebuffer the runtime draws into, owned by the display.
extern uint32_t *host_framebuffer;
extern int host_width, host_height;

uint32_t host_ticks_ms(void);
bool     host_quit_requested(void);
void     host_request_quit(void);
void     host_yield_to_main(void);
