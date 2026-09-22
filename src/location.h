// Where we are, for the weather. Needs the bundle: Location Services is refused
// to an unbundled binary, and the usage string lives in its Info.plist.
#pragma once
#include <stdbool.h>

// Ask for authorization and start watching, writing <data>/location.json as
// fixes arrive. Unbundled it says so and does nothing.
void location_start(const char *data);

void location_stop(void);
