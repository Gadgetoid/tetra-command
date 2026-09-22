#include <CoreFoundation/CoreFoundation.h>
#include <errno.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include "paths.h"

#define DATA_SUBDIR "/Library/Application Support/TetraCommand"

// Not CFBundle: it synthesises a bundle for a bare executable from whatever
// directory the binary sits in, so an Info.plist beside it reads as bundled.
// Only a real bundle puts the executable in Contents/MacOS.
bool paths_bundled(void) {
    char exe[PATH_MAX];
    uint32_t len = sizeof exe;
    if (_NSGetExecutablePath(exe, &len) != 0) return false;

    char resolved[PATH_MAX];
    if (!realpath(exe, resolved)) return false;

    char *slash = strrchr(resolved, '/');
    if (!slash) return false;
    *slash = '\0';

    char plist[PATH_MAX];
    if ((size_t)snprintf(plist, sizeof plist, "%s/../Info.plist", resolved) >= sizeof plist)
        return false;
    return access(plist, R_OK) == 0;
}

bool paths_resources(char *out, size_t len) {
    CFBundleRef bundle = CFBundleGetMainBundle();
    if (!bundle || !paths_bundled()) return false;

    CFURLRef url = CFBundleCopyResourcesDirectoryURL(bundle);
    if (!url) return false;
    CFURLRef absolute = CFURLCopyAbsoluteURL(url);
    CFRelease(url);
    if (!absolute) return false;

    bool ok = CFURLGetFileSystemRepresentation(absolute, true, (UInt8 *)out, len);
    CFRelease(absolute);
    return ok;
}

bool paths_data(char *out, size_t len) {
    const char *home = getenv("HOME");
    if (!home || !*home) return false;
    if ((size_t)snprintf(out, len, "%s%s", home, DATA_SUBDIR) >= len) return false;
    if (mkdir(out, 0755) != 0 && errno != EEXIST) return false;
    return true;
}
