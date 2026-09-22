// macOS touch input driver: reads the Weida digitizer directly via IOHIDManager.
//
// macOS never routes an external USB touchscreen anywhere, so SDL reports zero
// touch devices for this panel. We read the HID reports ourselves on a private
// thread with its own CFRunLoop and push normalised events into the host queue.
//
// Report ID 1 layout, decoded from the device's own report descriptor:
//   [0]        report id (1)
//   [1..50]    10 x finger: { tip:1, pad:2, contact_id:5 } { x_lo x_hi } { y_lo y_hi }
//   [51..52]   scan time (16-bit)
//   [53]       contact count
// X and Y are logical 0..0x7FFF across the panel.

#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/hid/IOHIDManager.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>

#include "input.h"

#define TETRA_VID 0x2575
#define TETRA_PID 0xfe13

#define FINGER_STRIDE    5
#define MAX_FINGERS     10
#define SCAN_TIME_BYTES  2
#define CONTACT_COUNT_OFFSET (MAX_FINGERS * FINGER_STRIDE + SCAN_TIME_BYTES)
#define LOGICAL_MAX 0x7fff

static bool contact_down[32];
static pthread_t hid_thread;
static CFRunLoopRef hid_runloop = NULL;
static bool seen_first_report = false;
static int panel_width = 1280, panel_height = 800;

static void on_report(void *ctx, IOReturn result, void *sender,
                      IOHIDReportType type, uint32_t report_id,
                      uint8_t *data, CFIndex len) {
    (void)ctx; (void)sender; (void)type;
    if (result != kIOReturnSuccess || len <= 0) return;

    // Some stacks include the report id as data[0], some strip it.
    CFIndex off = (len > 0 && data[0] == report_id) ? 1 : 0;
    if (report_id != 1) return;
    if (len - off < CONTACT_COUNT_OFFSET + 1) return;

    if (!seen_first_report) {
        seen_first_report = true;
        printf("[hid] first touch report received (len=%ld)\n", (long)len);
        fflush(stdout);
    }

    int count = data[off + CONTACT_COUNT_OFFSET];
    if (count < 0) count = 0;
    if (count > MAX_FINGERS) count = MAX_FINGERS;

    bool now_down[32] = { false };

    for (int i = 0; i < count; i++) {
        const uint8_t *f = data + off + i * FINGER_STRIDE;
        bool tip = f[0] & 0x01;
        int  cid = (f[0] >> 3) & 0x1f;
        int  rx  = f[1] | (f[2] << 8);
        int  ry  = f[3] | (f[4] << 8);

        uint16_t x = (uint16_t)((long)rx * (panel_width  - 1) / LOGICAL_MAX);
        uint16_t y = (uint16_t)((long)ry * (panel_height - 1) / LOGICAL_MAX);

        if (tip) {
            now_down[cid] = true;
            input_push(contact_down[cid] ? HOST_EV_MOVE : HOST_EV_DOWN,
                            (uint8_t)cid, x, y);
        } else if (contact_down[cid]) {
            input_push(HOST_EV_UP, (uint8_t)cid, x, y);
        }
    }

    // Any contact that vanished from the report has lifted.
    for (int cid = 0; cid < 32; cid++) {
        if (contact_down[cid] && !now_down[cid]) {
            input_push(HOST_EV_UP, (uint8_t)cid, 0, 0);
        }
    }
    memcpy(contact_down, now_down, sizeof(contact_down));
}

static CFMutableDictionaryRef match_dict(int vid, int pid) {
    CFMutableDictionaryRef d = CFDictionaryCreateMutable(
        kCFAllocatorDefault, 0, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
    CFNumberRef v = CFNumberCreate(kCFAllocatorDefault, kCFNumberIntType, &vid);
    CFNumberRef p = CFNumberCreate(kCFAllocatorDefault, kCFNumberIntType, &pid);
    CFDictionarySetValue(d, CFSTR(kIOHIDVendorIDKey), v);
    CFDictionarySetValue(d, CFSTR(kIOHIDProductIDKey), p);
    CFRelease(v); CFRelease(p);
    return d;
}

static uint8_t report_buf[128];

// Claimed as the manager reports them, not enumerated once at startup: the
// panel arrives as a new IOHIDDeviceRef every time it is plugged in, so a
// one-off pass leaves touch dead after the display is unplugged and back.
static void on_matched(void *ctx, IOReturn result, void *sender, IOHIDDeviceRef dev) {
    (void)ctx; (void)result; (void)sender;
    // Seize is required: macOS's own AppleUserHIDEventDriver claims this
    // device and input reports never reach an unseized client. (Feature
    // reports work either way, which makes this easy to misdiagnose.)
    IOReturn r = IOHIDDeviceOpen(dev, kIOHIDOptionsTypeSeizeDevice);
    if (r != kIOReturnSuccess) {
        fprintf(stderr, "[hid] IOHIDDeviceOpen(seize) failed: 0x%x\n", r);
        return;
    }
    IOHIDDeviceRegisterInputReportCallback(dev, report_buf, sizeof(report_buf),
                                           on_report, NULL);
    IOHIDDeviceScheduleWithRunLoop(dev, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);
    seen_first_report = false;
    printf("[hid] touch panel attached (%04x:%04x)\n", TETRA_VID, TETRA_PID);
    fflush(stdout);
}

static void on_removed(void *ctx, IOReturn result, void *sender, IOHIDDeviceRef dev) {
    (void)ctx; (void)result; (void)sender;
    // Let the departed device go: this panel is meant to be detached, so a run
    // loop source left scheduled per replug would pile up over a day of them.
    IOHIDDeviceUnscheduleFromRunLoop(dev, CFRunLoopGetCurrent(),
                                     kCFRunLoopDefaultMode);
    IOHIDDeviceRegisterInputReportCallback(dev, report_buf, sizeof(report_buf),
                                           NULL, NULL);
    IOHIDDeviceClose(dev, kIOHIDOptionsTypeSeizeDevice);

    // Anything still held has to be let go here: the panel is gone and cannot
    // report the lift, and a contact left down blocks its next touch.
    for (int cid = 0; cid < 32; cid++) {
        if (contact_down[cid]) {
            input_push(HOST_EV_UP, (uint8_t)cid, 0, 0);
        }
    }
    memset(contact_down, 0, sizeof(contact_down));
    printf("[hid] touch panel detached\n");
    fflush(stdout);
}

static void *hid_main(void *arg) {
    (void)arg;

    IOHIDManagerRef mgr = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);
    CFMutableDictionaryRef d = match_dict(TETRA_VID, TETRA_PID);
    IOHIDManagerSetDeviceMatching(mgr, d);
    CFRelease(d);

    IOHIDManagerRegisterDeviceMatchingCallback(mgr, on_matched, NULL);
    IOHIDManagerRegisterDeviceRemovalCallback(mgr, on_removed, NULL);
    // Scheduled before opening, so the devices already present arrive through
    // the same callback as the ones plugged in later.
    IOHIDManagerScheduleWithRunLoop(mgr, CFRunLoopGetCurrent(), kCFRunLoopDefaultMode);

    if (IOHIDManagerOpen(mgr, kIOHIDOptionsTypeNone) != kIOReturnSuccess) {
        fprintf(stderr, "[hid] IOHIDManagerOpen failed\n");
        return NULL;
    }

    hid_runloop = CFRunLoopGetCurrent();
    fflush(stdout);
    CFRunLoopRun();
    return NULL;
}

static bool hid_init(int width, int height) {
    panel_width = width; panel_height = height;
    return pthread_create(&hid_thread, NULL, hid_main, NULL) == 0;
}

static void hid_deinit(void) {
    if (hid_runloop) {
        CFRunLoopStop(hid_runloop);
        pthread_join(hid_thread, NULL);
        hid_runloop = NULL;
    }
}

const input_driver_t input_driver_hid_macos = {
    .name   = "hid-macos",
    .init   = hid_init,
    .deinit = hid_deinit,
};
