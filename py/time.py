"""Time functions backed by the host clock."""

import host


def localtime(secs=None):
    return host.localtime()


def time():
    return host.epoch()


def ticks_ms():
    return host.ticks_ms()


def ticks_diff(a, b):
    return a - b


def ticks_add(a, b):
    return a + b
