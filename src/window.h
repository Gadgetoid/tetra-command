// Covering a display without going through macOS fullscreen.
#pragma once
#include <stdbool.h>

// Raise a window above the menu bar, so one sized to a display's bounds covers
// all of it. Takes the NSWindow as the void * SDL hands out.
bool window_raise_above_menu_bar(void *nswindow);
