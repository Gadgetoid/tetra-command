// Functions picovector expects from Pimoroni's MicroPython fork that upstream
// does not provide.
#include "py/runtime.h"
#include "py/gc.h"

// The fork allocates pointer-free data (pixel and vertex buffers) with a GC
// no-scan flag. Upstream's gc_alloc has no such flag, so these allocations are
// scanned conservatively: correct, but the GC walks large buffers it never needs
// to, which costs collection time and can falsely retain objects.
// Swap to the fork, or add GC_ALLOC_FLAG_NO_SCAN upstream, to get this back.
void *m_malloc_no_scan(size_t num_bytes) {
    return m_malloc(num_bytes);
}

// The embed port ships no timebase; picovector.config.hpp maps PV_TICKS to this.
extern uint32_t host_ticks_ms(void);
mp_uint_t mp_hal_ticks_ms(void) {
    return host_ticks_ms();
}
