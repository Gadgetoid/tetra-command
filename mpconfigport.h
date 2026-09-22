#include <stddef.h>
#include <port/mpconfigport_common.h>

// Provided by src/runtime/mp_shims.c; see there for why.
void *m_malloc_no_scan(size_t num_bytes);

#define MICROPY_CONFIG_ROM_LEVEL        (MICROPY_CONFIG_ROM_LEVEL_EXTRA_FEATURES)

#define MICROPY_ENABLE_COMPILER         (1)
#define MICROPY_ENABLE_GC               (1)
#define MICROPY_PY_GC                   (1)
#define MICROPY_PY_SYS                  (1)
#define MICROPY_PY_SYS_PLATFORM         "macropad"
#define MICROPY_PY_TIME                 (1)
#define MICROPY_FLOAT_IMPL              (MICROPY_FLOAT_IMPL_FLOAT)
#define MICROPY_ERROR_REPORTING         (MICROPY_ERROR_REPORTING_NORMAL)
#define MICROPY_ENABLE_SOURCE_LINE      (1)
#define MICROPY_ENABLE_EXTERNAL_IMPORT  (1)

// Filesystem: the app directory is mounted as / so import and open() work.
// MICROPY_VFS makes py/builtin.h route mp_builtin_open_obj and mp_import_stat
// at the VFS automatically.
#define MICROPY_PY_IO                   (1)
#define MICROPY_VFS                     (1)
#define MICROPY_VFS_POSIX               (1)
#define MICROPY_READER_VFS              (1)
#define MICROPY_ENABLE_FINALISER        (1)
#define MICROPY_TRACKED_ALLOC           (1)   // picovector's JPEG decoder uses m_tracked_calloc
#define MICROPY_PY_OS                   (1)

// EXTRA_FEATURES turns these on, but they need port pieces we do not have:
// uctypes is not compiled, and input() wants a readline/stdin this host has none of.
#define MICROPY_PY_UCTYPES              (0)
#define MICROPY_PY_BUILTINS_INPUT       (0)
#define MICROPY_PY_SYS_STDFILES         (0)

#define MICROPY_KBD_EXCEPTION           (1)
void mp_hal_set_interrupt_char(int c);
#define MICROPY_ENABLE_SCHEDULER        (1)

extern void host_vm_hook(void);
#define MICROPY_VM_HOOK_COUNT (256)
#define MICROPY_VM_HOOK_INIT  static uint32_t vm_hook_divisor = MICROPY_VM_HOOK_COUNT;
#define MICROPY_VM_HOOK_POLL  if (--vm_hook_divisor == 0) { \
                                  vm_hook_divisor = MICROPY_VM_HOOK_COUNT; \
                                  host_vm_hook(); \
                              }
#define MICROPY_VM_HOOK_LOOP  MICROPY_VM_HOOK_POLL
#define MICROPY_VM_HOOK_RETURN MICROPY_VM_HOOK_POLL

// POSIX glue that extmod/vfs_posix.c expects the port to provide. The unix
// port defines these in its mphalport.h; the embed port has no equivalent.
// No GIL here, so the unix port's thread macros are dropped.
#define MP_HAL_RETRY_SYSCALL(ret, syscall, raise) { \
        for (;;) { \
            ret = syscall; \
            if (ret == -1) { \
                int err = errno; \
                if (err == EINTR) { \
                    mp_handle_pending(MP_HANDLE_PENDING_CALLBACKS_AND_EXCEPTIONS); \
                    continue; \
                } \
                raise; \
            } \
            break; \
        } \
}

#define RAISE_ERRNO(err_flag, error_val) \
    { if (err_flag == -1) { mp_raise_OSError(error_val); } }
