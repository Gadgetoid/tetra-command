"""HID keycodes and macro helpers.

A macro is a generator. Each step it yields whatever is held right now:

    an int         one key
    a tuple/list   a chord
    0              release everything
    DO_NOTHING     leave the held set alone
    a generator    a sub-macro, run to exhaustion before this one continues
"""

import time


class KC:
    A = 4
    B = 5
    C = 6
    D = 7
    E = 8
    F = 9
    G = 10
    H = 11
    I = 12
    J = 13
    K = 14
    L = 15
    M = 16
    N = 17
    O = 18
    P = 19
    Q = 20
    R = 21
    S = 22
    T = 23
    U = 24
    V = 25
    W = 26
    X = 27
    Y = 28
    Z = 29
    N1 = 30
    N2 = 31
    N3 = 32
    N4 = 33
    N5 = 34
    N6 = 35
    N7 = 36
    N8 = 37
    N9 = 38
    N0 = 39
    ENTER = 40
    ESCAPE = 41
    BACKSPACE = 42
    TAB = 43
    SPACE = 44
    MINUS = 45
    EQUAL = 46
    OPEN_BRACKET = 47
    CLOSE_BRACKET = 48
    BACKSLASH = 49
    HASH = 50
    SEMICOLON = 51
    QUOTE = 52
    GRAVE = 53
    COMMA = 54
    DOT = 55
    SLASH = 56
    CAPS_LOCK = 57
    F1 = 58
    F2 = 59
    F3 = 60
    F4 = 61
    F5 = 62
    F6 = 63
    F7 = 64
    F8 = 65
    F9 = 66
    F10 = 67
    F11 = 68
    F12 = 69
    INSERT = 73
    HOME = 74
    PAGEUP = 75
    DELETE = 76
    END = 77
    PAGEDOWN = 78
    RIGHT = 79
    LEFT = 80
    DOWN = 81
    UP = 82
    LEFT_CTRL = 0xE0
    LEFT_SHIFT = 0xE1
    LEFT_ALT = 0xE2
    LEFT_UI = 0xE3
    RIGHT_CTRL = 0xE4
    RIGHT_SHIFT = 0xE5
    RIGHT_ALT = 0xE6
    RIGHT_UI = 0xE7


DO_NOTHING = -1

charmap = {
    9: KC.TAB,
    10: KC.ENTER,
    32: KC.SPACE,
    33: (KC.LEFT_SHIFT, KC.N1),
    34: (KC.LEFT_SHIFT, KC.QUOTE),
    35: (KC.HASH),
    36: (KC.LEFT_SHIFT, KC.N4),
    37: (KC.LEFT_SHIFT, KC.N5),
    38: (KC.LEFT_SHIFT, KC.N7),
    39: (KC.QUOTE),
    40: (KC.LEFT_SHIFT, KC.N9),
    41: (KC.LEFT_SHIFT, KC.N0),
    42: (KC.LEFT_SHIFT, KC.N8),
    43: (KC.LEFT_SHIFT, KC.EQUAL),
    44: KC.COMMA,
    45: KC.MINUS,
    46: KC.DOT,
    47: KC.SLASH,
    58: (KC.LEFT_SHIFT, KC.SEMICOLON),
    59: KC.SEMICOLON,
    60: (KC.LEFT_SHIFT, KC.COMMA),
    61: KC.EQUAL,
    62: (KC.LEFT_SHIFT, KC.DOT),
    63: (KC.LEFT_SHIFT, KC.SLASH),
    64: (KC.LEFT_SHIFT, KC.N2),
    91: KC.OPEN_BRACKET,
    92: KC.BACKSLASH,
    93: KC.CLOSE_BRACKET,
    94: (KC.LEFT_SHIFT, KC.N6),
    95: (KC.LEFT_SHIFT, KC.MINUS),
    123: (KC.LEFT_SHIFT, KC.OPEN_BRACKET),
    124: (KC.LEFT_SHIFT, KC.BACKSLASH),
    125: (KC.LEFT_SHIFT, KC.CLOSE_BRACKET),
    126: (KC.LEFT_SHIFT, KC.GRAVE),
    163: (KC.LEFT_SHIFT, KC.N3),
}

a_to_z = range(ord("a"), ord("z") + 1)
one_to_nine = range(ord("1"), ord("9") + 1)


def wait(delay):
    if delay == 0:
        return
    t_until = time.ticks_ms() + delay
    if time.ticks_diff(t_until, time.ticks_ms()) > 0:
        yield 0
    while time.ticks_diff(t_until, time.ticks_ms()) > 0:
        yield DO_NOTHING


def hold(key, delay, auto_release=True):
    t_until = time.ticks_ms() + delay
    while time.ticks_diff(t_until, time.ticks_ms()) > 0:
        yield key
    if auto_release:
        yield 0


def repeat(key, times, delay=0):
    for _ in range(times):
        yield key
        yield 0
        yield wait(delay)


def scancode(char):
    upper = char.isupper()
    char = ord(char.lower())
    if char in a_to_z:
        if upper:
            return KC.LEFT_SHIFT, char - 97 + KC.A
        return char - 97 + KC.A
    elif char in one_to_nine:
        return char - 49 + KC.N1
    elif char == 48:
        return KC.N0
    k = charmap.get(char)
    return k if k else 0


def text(value, delay=16):
    """Type a string."""
    last_key = None
    for char in value:
        sc = scancode(char)
        if isinstance(sc, tuple):
            mod, key = sc
            if key == last_key:
                yield 0
            last_key = key
            yield mod
            yield mod, key
        else:
            if sc == last_key:
                yield 0
            last_key = sc
            yield sc
        yield wait(delay)


def chord(*codes):
    """Press a combination, then let go."""
    yield tuple(codes)
    yield 0
