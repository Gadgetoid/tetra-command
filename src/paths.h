// Where the app tree and the writable data directory are.
#pragma once
#include <stdbool.h>
#include <stddef.h>

// Whether we are running from a real bundle.
bool paths_bundled(void);

// Contents/Resources of the running bundle. False when unbundled.
bool paths_resources(char *out, size_t len);

// ~/Library/Application Support/TetraCommand, created if missing. Kept in step
// with tools/paths.py.
bool paths_data(char *out, size_t len);
