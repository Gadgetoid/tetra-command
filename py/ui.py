"""Layout roles and metrics every settings page draws from."""

import draw
import look


def TITLE():
    return look.SIZE_TITLE


def SECTION():
    return look.SIZE_SMALL


def HEADING():
    return SECTION()


def CAPTION():
    return look.SIZE_SMALL


def CONTROL():
    """Return the size for text in or beside a control."""
    return look.SIZE_SMALL


def READOUT():
    return look.SIZE_BIG


def MARGIN():
    """Return the inset on every side of every page."""
    return look.PAD


def GAP():
    """Return the gap between peers."""
    return look.px(8)


def BAND():
    """Return the vertical room a heading takes."""
    return look.px(24)


def CONTROL_H():
    """Return the height of a button or tab."""
    return look.px(26)


def SWITCH_H():
    """Return the height of a toggle switch."""
    return CONTROL() + look.px(5)


def CAPTION_BAND():
    """Return the room a caption under a tile takes."""
    return look.px(16)


def CORNER():
    """Return the corner radius for a tile or swatch."""
    return look.px(4)


def RULE():
    """Return the thickness of a divider."""
    return max(2, look.px(2))


def frame():
    """Return the content box as (left, top, right, bottom)."""
    margin = MARGIN()
    return (margin, look.BODY_TOP + margin,
            look.W - margin, look.BODY_TOP + look.BODY_H - margin)


def columns(count, gap=None, left=None, right=None):
    """Return (width, x_of) for `count` equal columns across the content box."""
    step = GAP() if gap is None else gap
    edge_l = MARGIN() if left is None else left
    edge_r = (look.W - MARGIN()) if right is None else right
    width = (edge_r - edge_l - step * (count - 1)) // count
    return width, lambda i: edge_l + i * (width + step)


_caption = None


def plan_captions(sets):
    """Fix the one caption size the whole app draws at, given (texts, room) pairs."""
    global _caption
    size = CAPTION()
    for texts, room in sets:
        size = min(size, uniform_size(texts, size, room))
    _caption = size
    return size


def CAPTION_FITTED():
    return CAPTION() if _caption is None else _caption


def uniform_size(texts, size, room, name=draw.TEXT):
    """Return the largest size at which every text in the set fits."""
    for text in texts:
        if text:
            size = min(size, draw.fit_size(text, size, room, name))
    return size
