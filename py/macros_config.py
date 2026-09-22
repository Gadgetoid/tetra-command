"""The macro pad, as data.

A button is a label, a Material Symbols codepoint, and one of:

    "macro"  run once, on tap
    "hold"   run while your finger stays down
    "modal"  a sheet of further options, each with a macro of its own

Macros are generators (see keys.py); each step yields whatever is held now.
"""

from keys import KC, chord, text, wait

COLS, ROWS = 4, 2


def spotlight():
    yield from chord(KC.LEFT_UI, KC.SPACE)


def copy():
    yield from chord(KC.LEFT_UI, KC.C)


def paste():
    yield from chord(KC.LEFT_UI, KC.V)


def lock_screen():
    yield from chord(KC.LEFT_UI, KC.LEFT_CTRL, KC.Q)


def signature():
    yield from text("Sent from my 8 inch touchscreen. ")
    yield from wait(120)
    yield from text("Regards, Phil")


def switcher_hold():
    """Hold cmd and step the app switcher every 600ms."""
    yield KC.LEFT_UI
    yield KC.LEFT_UI, KC.TAB
    yield KC.LEFT_UI
    while True:
        yield from wait(600)
        yield KC.LEFT_UI, KC.TAB
        yield KC.LEFT_UI


def shot_region():
    yield from chord(KC.LEFT_UI, KC.LEFT_SHIFT, KC.N4)


def shot_window():
    """Select a region, then press space to switch to window capture."""
    yield from chord(KC.LEFT_UI, KC.LEFT_SHIFT, KC.N4)
    yield from wait(220)
    yield from chord(KC.SPACE)


def shot_full():
    yield from chord(KC.LEFT_UI, KC.LEFT_SHIFT, KC.N3)


def shot_record():
    """Open the capture and recording toolbar."""
    yield from chord(KC.LEFT_UI, KC.LEFT_SHIFT, KC.N5)


def mission_control():
    yield from chord(KC.LEFT_CTRL, KC.UP)


def app_windows():
    yield from chord(KC.LEFT_CTRL, KC.DOWN)


def space_left():
    yield from chord(KC.LEFT_CTRL, KC.LEFT)


def space_right():
    yield from chord(KC.LEFT_CTRL, KC.RIGHT)


BUTTONS = [
    {"label": "Spotlight",  "icon": "\uef7a", "macro": spotlight},
    {"label": "Windows",    "icon": "\ue9b0", "modal": [
        {"label": "Mission",  "icon": "\ue871", "macro": mission_control},
        {"label": "App",      "icon": "\ue069", "macro": app_windows},
        {"label": "Space ←", "icon": "\ue5c4", "macro": space_left},
        {"label": "Space →", "icon": "\ue5c8", "macro": space_right},
    ]},
    {"label": "Screenshot", "icon": "\uf7d2", "modal": [
        {"label": "Region",   "icon": "\ue3c2", "macro": shot_region},
        {"label": "Window",   "icon": "\ue069", "macro": shot_window},
        {"label": "Full",     "icon": "\ue5d0", "macro": shot_full},
        {"label": "Record",   "icon": "\ue04b", "macro": shot_record},
    ]},
    {"label": "Switcher",   "icon": "\ue5c3", "hold": switcher_hold},
    {"label": "Copy",       "icon": "\ue14d", "macro": copy},
    {"label": "Paste",      "icon": "\ue14f", "macro": paste},
    {"label": "Sign-off",   "icon": "\ueb8e", "macro": signature},
    {"label": "Lock",       "icon": "\ue899", "macro": lock_screen},
]


def _icons(entries):
    out = ""
    for entry in entries:
        out += entry.get("icon", "")
        out += _icons(entry.get("modal", ()))
    return out


ICON_CHARS = _icons(BUTTONS)
