#pragma once
#include "host.h"

bool display_init(const macropad_config_t *cfg);
void display_deinit(void);

// Uploads the framebuffer and presents one frame.
void display_present_frame(void);

// Drains OS window events. Returns false when the user asked to quit.
// SDL pointer events are pushed into the input queue as the fallback driver.
bool display_pump_events(void);

void display_list(void);
