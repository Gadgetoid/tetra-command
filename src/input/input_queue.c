#include <SDL3/SDL.h>
#include "input.h"

#define EVQ_SIZE 512

static host_event_t evq[EVQ_SIZE];
static size_t head = 0, tail = 0;
static SDL_Mutex *lock = NULL;

void input_queue_init(void) { lock = SDL_CreateMutex(); }

void input_queue_deinit(void) {
    if (lock) { SDL_DestroyMutex(lock); lock = NULL; }
}

void input_push(uint8_t kind, uint8_t finger, uint16_t x, uint16_t y) {
    if (!lock) return;
    SDL_LockMutex(lock);
    size_t next = (head + 1) % EVQ_SIZE;
    if (next != tail) {
        evq[head] = (host_event_t){ kind, finger, x, y };
        head = next;
    }
    SDL_UnlockMutex(lock);
}

bool input_pop(host_event_t *out) {
    if (!lock) return false;
    bool got = false;
    SDL_LockMutex(lock);
    if (tail != head) {
        *out = evq[tail];
        tail = (tail + 1) % EVQ_SIZE;
        got = true;
    }
    SDL_UnlockMutex(lock);
    return got;
}

#if defined(__APPLE__)
extern const input_driver_t input_driver_hid_macos;
#endif

static const input_driver_t *drivers[] = {
    #if defined(__APPLE__)
    &input_driver_hid_macos,
    #endif
};

void input_init_all(int width, int height) {
    for (size_t i = 0; i < sizeof(drivers) / sizeof(drivers[0]); i++) {
        const input_driver_t *d = drivers[i];
        bool ok = d->init(width, height);
        SDL_Log("input: %-10s %s", d->name, ok ? "ready" : "unavailable");
    }
}

void input_deinit_all(void) {
    for (size_t i = 0; i < sizeof(drivers) / sizeof(drivers[0]); i++) {
        drivers[i]->deinit();
    }
}
