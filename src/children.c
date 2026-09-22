#include <errno.h>
#include <signal.h>
#include <spawn.h>
#include <stdio.h>
#include <string.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#include "children.h"

extern char **environ;

// How long to wait for a SIGTERM to take, before insisting.
#define STOP_TRIES 50
#define STOP_STEP_NS (10 * 1000 * 1000L)

#define MAX_CHILDREN 4
#define MAX_ARGS 12

static pid_t children[MAX_CHILDREN];
static int count = 0;

bool child_spawn(const char *python, const char *script, const char *const *args) {
    if (count >= MAX_CHILDREN) return false;
    if (access(python, X_OK) != 0 || access(script, R_OK) != 0) {
        fprintf(stderr, "children: not starting, no %s\n",
                access(python, X_OK) != 0 ? python : script);
        return false;
    }

    // -B: a __pycache__ written into the bundle breaks its signature.
    char *argv[MAX_ARGS];
    int n = 0;
    argv[n++] = (char *)python;
    argv[n++] = "-B";
    argv[n++] = (char *)script;
    for (int i = 0; args && args[i]; i++) {
        if (n >= MAX_ARGS - 1) break;
        argv[n++] = (char *)args[i];
    }
    argv[n] = NULL;

    pid_t child;
    int err = posix_spawn(&child, python, NULL, NULL, argv, environ);
    if (err != 0) {
        fprintf(stderr, "children: cannot spawn %s: %s\n", script, strerror(err));
        return false;
    }
    children[count++] = child;
    return true;
}

static void stop_one(pid_t child) {
    kill(child, SIGTERM);
    for (int attempt = 0; attempt < STOP_TRIES; attempt++) {
        int status;
        pid_t done = waitpid(child, &status, WNOHANG);
        if (done == child || (done < 0 && errno != EINTR)) return;
        nanosleep(&(struct timespec){ .tv_nsec = STOP_STEP_NS }, NULL);
    }
    kill(child, SIGKILL);
    waitpid(child, NULL, 0);
}

void children_stop(void) {
    // Every SIGTERM first, so the waits overlap rather than stacking up.
    for (int i = 0; i < count; i++) kill(children[i], SIGTERM);
    for (int i = 0; i < count; i++) stop_one(children[i]);
    count = 0;
}
