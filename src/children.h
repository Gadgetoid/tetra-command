// The host-side tools, run as children for as long as the app lives: the stats
// sampler, and the weather fetch that follows Location Services.
#pragma once
#include <stdbool.h>

// Spawn `python script args...`. False if either path is missing, which is not
// fatal: the pages say they have no data.
bool child_spawn(const char *python, const char *script, const char *const *args);

// Ask every child to stop, then reap them. Safe to call having started none.
void children_stop(void);
