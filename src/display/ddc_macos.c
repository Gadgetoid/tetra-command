// DDC/CI on Apple Silicon, over the DisplayPort AUX channel's I2C.
//
// There is no public API for this. The DisplayPort transport hangs off
// IOAVService, whose three I2C calls are exported from IOKit but absent from
// its headers, so they are declared by hand below. Same route m1ddc takes.
//
// The wire protocol is MCCS over I2C at chip 0x37, with every message written
// to and read from register 0x51. Checksums seed with the destination address
// (0x6e, which is 0x37 shifted up one) xored with that register.
//
//   get request   82 01 <vcp> <cksum>
//   get reply     6e 88 02 <result> <vcp> <type> <max hi> <max lo> <cur hi> <cur lo> <cksum>
//   set request   84 03 <vcp> <val hi> <val lo> <cksum>
//
// A non-zero result byte means the panel does not implement that code. The bus
// is slow and occasionally drops a transaction, hence the retries, and the spec
// wants 50ms of quiet between messages.
//
// Writes are handed to a worker thread. A DDC write costs ~50ms of settle time,
// which is three dropped frames on the render thread, and a dragged slider
// produces far more updates than the bus can carry, so the worker keeps one
// pending value per code and always writes the newest.

#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#include <time.h>
#include <strings.h>
#include <unistd.h>

#include "ddc.h"

typedef CFTypeRef IOAVServiceRef;
extern IOAVServiceRef IOAVServiceCreateWithService(CFAllocatorRef, io_service_t);
extern IOReturn IOAVServiceReadI2C(IOAVServiceRef, uint32_t, uint32_t, void *, uint32_t);
extern IOReturn IOAVServiceWriteI2C(IOAVServiceRef, uint32_t, uint32_t, void *, uint32_t);

#define DDC_CHIP        0x37
#define DDC_REGISTER    0x51
#define DDC_DEST_ADDR   0x6e
#define EDID_CHIP       0x50

#define REPLY_DELAY_US  50000
#define SETTLE_DELAY_US 50000
#define BUS_RETRIES     3

#define VCP_COUNT       256
#define EDID_BLOCK      128
#define EDID_DESC_FIRST 54
#define EDID_DESC_LAST  108
#define EDID_DESC_SIZE  18
#define EDID_TAG_NAME   0xfc

static IOAVServiceRef service = NULL;

// The display this app was asked for, kept so the service can be found again.
// Unplugging the panel invalidates the IOAVService and plugging it back in
// makes a new one, so holding the first for the life of the process left the
// OSD page reporting no DDC/CI until a restart.
static char wanted_display[64];

// How often to go back to the registry looking for it, once it has gone. A
// scan reads each candidate's EDID, so this is not something to do per frame.
#define REOPEN_EVERY_MS 1000
static uint64_t last_attempt_ms;

static uint64_t now_ms(void) {
    struct timespec at;
    clock_gettime(CLOCK_MONOTONIC, &at);
    return (uint64_t)at.tv_sec * 1000 + at.tv_nsec / 1000000;
}


// Guards the hardware. Held across a whole request/reply pair so a read from
// the render thread cannot interleave with the worker's write.
static pthread_mutex_t bus_lock = PTHREAD_MUTEX_INITIALIZER;

// Guards the table below, and the worker's run flag.
static pthread_mutex_t state_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t  state_wake = PTHREAD_COND_INITIALIZER;

static struct {
    int  value;      // last value written or read, -1 when never seen
    int  maximum;    // -1 until a read tells us
    bool queued;
} vcp[VCP_COUNT];

static pthread_t worker;
static bool worker_started = false;
static bool running = false;

// One 18-byte EDID descriptor carries the monitor name under tag 0xfc, padded
// with spaces and sometimes terminated with a newline.
static bool edid_name_matches(const uint8_t *edid, const char *want) {
    for (int base = EDID_DESC_FIRST; base <= EDID_DESC_LAST; base += EDID_DESC_SIZE) {
        if (edid[base] || edid[base + 1] || edid[base + 2] || edid[base + 4]) continue;
        if (edid[base + 3] != EDID_TAG_NAME) continue;

        char name[14] = { 0 };
        memcpy(name, edid + base + 5, 13);
        for (char *p = name; *p; p++) {
            if (*p == '\n') { *p = '\0'; break; }
        }
        if (strcasestr(name, want)) return true;
    }
    return false;
}

// Every external display is a DCPAVServiceProxy in the registry. Which one is
// ours is settled by reading each candidate's EDID, matching the display name
// the same way display_sdl.c does.
static IOAVServiceRef open_service_for(const char *display_name) {
    io_iterator_t iter;
    if (IOServiceGetMatchingServices(kIOMainPortDefault,
            IOServiceMatching("DCPAVServiceProxy"), &iter) != kIOReturnSuccess) {
        return NULL;
    }

    IOAVServiceRef found = NULL;
    io_service_t entry;
    while ((entry = IOIteratorNext(iter))) {
        if (found) { IOObjectRelease(entry); continue; }

        CFStringRef location = IORegistryEntryCreateCFProperty(
            entry, CFSTR("Location"), kCFAllocatorDefault, 0);
        bool external = location
            && CFStringCompare(location, CFSTR("External"), 0) == kCFCompareEqualTo;
        if (location) CFRelease(location);

        if (external) {
            IOAVServiceRef candidate = IOAVServiceCreateWithService(kCFAllocatorDefault, entry);
            if (candidate) {
                uint8_t edid[EDID_BLOCK];
                if (IOAVServiceReadI2C(candidate, EDID_CHIP, 0, edid, sizeof(edid)) == kIOReturnSuccess
                    && edid_name_matches(edid, display_name)) {
                    found = candidate;
                } else {
                    CFRelease(candidate);
                }
            }
        }
        IOObjectRelease(entry);
    }
    IOObjectRelease(iter);
    return found;
}

static void forget_service(void) {
    if (service) {
        CFRelease(service);
        service = NULL;
    }
    // The readings belonged to the panel that left; a new one is read afresh.
    pthread_mutex_lock(&state_lock);
    for (int i = 0; i < VCP_COUNT; i++) {
        vcp[i].value = -1;
        vcp[i].maximum = -1;
    }
    pthread_mutex_unlock(&state_lock);
}


// Called with bus_lock held: one re-open attempt at a time.
static bool ensure_service(void) {
    if (service) return true;
    if (!wanted_display[0]) return false;
    uint64_t at = now_ms();
    if (last_attempt_ms && at - last_attempt_ms < REOPEN_EVERY_MS) return false;
    last_attempt_ms = at;
    service = open_service_for(wanted_display);
    if (service) {
        printf("[ddc] display '%s' back, DDC/CI reacquired\n", wanted_display);
        fflush(stdout);
    }
    return service != NULL;
}


// Both of these run with bus_lock held.
static bool bus_get(uint8_t code, int *current, int *maximum) {
    if (!ensure_service()) return false;
    uint8_t request[4] = { 0x82, 0x01, code, 0 };
    request[3] = DDC_DEST_ADDR ^ DDC_REGISTER ^ request[0] ^ request[1] ^ request[2];

    for (int attempt = 0; attempt < BUS_RETRIES; attempt++) {
        if (IOAVServiceWriteI2C(service, DDC_CHIP, DDC_REGISTER,
                                request, sizeof(request)) != kIOReturnSuccess) {
            continue;
        }
        usleep(REPLY_DELAY_US);

        uint8_t reply[12] = { 0 };
        if (IOAVServiceReadI2C(service, DDC_CHIP, DDC_REGISTER,
                               reply, sizeof(reply)) != kIOReturnSuccess) {
            continue;
        }
        if (reply[0] != DDC_DEST_ADDR || reply[3] != 0x00 || reply[4] != code) continue;

        if (maximum) *maximum = (reply[6] << 8) | reply[7];
        if (current) *current = (reply[8] << 8) | reply[9];
        return true;
    }
    // Every retry failed. The panel may simply not implement this code, so the
    // service is only dropped where the bus itself has stopped answering.
    uint8_t probe[12] = { 0 };
    if (IOAVServiceReadI2C(service, EDID_CHIP, 0, probe, sizeof(probe))
            != kIOReturnSuccess) {
        forget_service();
    }
    return false;
}

static void bus_set(uint8_t code, int value) {
    if (!ensure_service()) return;
    uint8_t request[6] = {
        0x84, 0x03, code, (uint8_t)((value >> 8) & 0xff), (uint8_t)(value & 0xff), 0
    };
    request[5] = DDC_DEST_ADDR ^ DDC_REGISTER ^ request[0] ^ request[1]
               ^ request[2] ^ request[3] ^ request[4];

    if (IOAVServiceWriteI2C(service, DDC_CHIP, DDC_REGISTER, request,
                            sizeof(request)) != kIOReturnSuccess) {
        forget_service();
        return;
    }
    usleep(SETTLE_DELAY_US);
}

// Drains everything queued before honouring a stop, so a brightness change made
// on the way out still lands.
static void *worker_main(void *arg) {
    (void)arg;
    pthread_mutex_lock(&state_lock);
    for (;;) {
        int code = -1, value = 0;
        for (int i = 0; i < VCP_COUNT; i++) {
            if (vcp[i].queued) {
                vcp[i].queued = false;
                code = i;
                value = vcp[i].value;
                break;
            }
        }

        if (code >= 0) {
            pthread_mutex_unlock(&state_lock);
            pthread_mutex_lock(&bus_lock);
            bus_set((uint8_t)code, value);
            pthread_mutex_unlock(&bus_lock);
            pthread_mutex_lock(&state_lock);
            continue;
        }

        if (!running) break;
        pthread_cond_wait(&state_wake, &state_lock);
    }
    pthread_mutex_unlock(&state_lock);
    return NULL;
}

bool ddc_init(const macropad_config_t *cfg) {
    for (int i = 0; i < VCP_COUNT; i++) {
        vcp[i].value = -1;
        vcp[i].maximum = -1;
        vcp[i].queued = false;
    }

    snprintf(wanted_display, sizeof(wanted_display), "%s",
             cfg->display_name ? cfg->display_name : "");
    service = open_service_for(wanted_display);
    if (!service) {
        // Not fatal: the panel may arrive later, and ensure_service will find
        // it. The worker still starts so a write made before then is queued.
        printf("[ddc] no DDC/CI service matching '%s' yet; will keep looking\n",
               wanted_display);
    }

    running = true;
    if (pthread_create(&worker, NULL, worker_main, NULL) != 0) {
        printf("[ddc] could not start worker thread\n");
        running = false;
        forget_service();
        return false;
    }
    worker_started = true;
    return true;
}

void ddc_deinit(void) {
    if (worker_started) {
        pthread_mutex_lock(&state_lock);
        running = false;
        pthread_cond_signal(&state_wake);
        pthread_mutex_unlock(&state_lock);
        pthread_join(worker, NULL);
        worker_started = false;
    }
    if (service) {
        CFRelease(service);
        service = NULL;
    }
}

bool ddc_available(void) {
    // Cheap: a caller asking every frame must not trigger a registry scan.
    // ddc_get re-acquires, so a page that retries its read recovers on its own.
    return service != NULL || wanted_display[0] != 0;
}

bool ddc_get(uint8_t code, int *current, int *maximum) {
    pthread_mutex_lock(&state_lock);
    if (vcp[code].value >= 0 && vcp[code].maximum >= 0) {
        if (current) *current = vcp[code].value;
        if (maximum) *maximum = vcp[code].maximum;
        pthread_mutex_unlock(&state_lock);
        return true;
    }
    pthread_mutex_unlock(&state_lock);

    int read_current = 0, read_maximum = 0;
    pthread_mutex_lock(&bus_lock);
    bool ok = bus_get(code, &read_current, &read_maximum);
    pthread_mutex_unlock(&bus_lock);
    if (!ok) return false;

    pthread_mutex_lock(&state_lock);
    vcp[code].maximum = read_maximum;
    // A write may have been queued while the bus was busy; that value is newer.
    if (vcp[code].value < 0) vcp[code].value = read_current;
    if (current) *current = vcp[code].value;
    pthread_mutex_unlock(&state_lock);

    if (maximum) *maximum = read_maximum;
    return true;
}

void ddc_set(uint8_t code, int value) {
    if (!service) return;

    pthread_mutex_lock(&state_lock);
    if (value < 0) value = 0;
    if (vcp[code].maximum >= 0 && value > vcp[code].maximum) value = vcp[code].maximum;
    vcp[code].value = value;
    vcp[code].queued = true;
    pthread_cond_signal(&state_wake);
    pthread_mutex_unlock(&state_lock);
}
