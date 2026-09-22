#pragma once
#include "host.h"

bool runtime_init(const macropad_config_t *cfg);
void runtime_deinit(void);

// Resumes the Python fiber until it calls host.present() or finishes.
// Returns false once the script has exited.
bool runtime_step(void);

bool runtime_finished(void);
