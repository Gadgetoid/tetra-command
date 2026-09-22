#pragma once
#include "host.h"

// An input driver turns platform touch/pointer events into host events.
// Drivers push into a shared queue; the frame loop drains it.
typedef struct {
    const char *name;
    bool (*init)(int width, int height);
    void (*deinit)(void);
} input_driver_t;

void input_queue_init(void);
void input_queue_deinit(void);
void input_push(uint8_t kind, uint8_t finger, uint16_t x, uint16_t y);
bool input_pop(host_event_t *out);

// Brings up every driver available on this platform. Drivers that find no
// hardware simply report so and are skipped; SDL mouse always works.
void input_init_all(int width, int height);
void input_deinit_all(void);
