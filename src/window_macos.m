#import <Cocoa/Cocoa.h>

#include "window.h"

bool window_raise_above_menu_bar(void *handle) {
    NSWindow *window = (__bridge NSWindow *)handle;
    if (!window) return false;

    // Higher levels also cover notifications and the force-quit dialog.
    window.level = NSMainMenuWindowLevel + 1;

    // FullScreenNone keeps AppKit from making a fullscreen Space of its own.
    window.collectionBehavior = NSWindowCollectionBehaviorCanJoinAllSpaces
                              | NSWindowCollectionBehaviorStationary
                              | NSWindowCollectionBehaviorFullScreenNone;

    NSRect frame = window.frame;
    NSLog(@"display: covering %.0fx%.0f at %.0f,%.0f, window level %ld",
          frame.size.width, frame.size.height, frame.origin.x, frame.origin.y,
          (long)window.level);
    return true;
}
