"""Theme colours and the 320x240 layout."""

W = 320
H = 240

HEADER_H = 30
FOOTER_H = 20
BODY_TOP = HEADER_H
BODY_H = H - HEADER_H - FOOTER_H
BODY_MID = BODY_TOP + BODY_H // 2

PAD = 10

DIAL_GAP = 16
DIAL_OUTER = 82
DIAL_INNER = 62
DIAL_C = (DIAL_GAP + DIAL_OUTER, BODY_TOP + BODY_H // 2 + 2)
DIAL_FROM = 225.0
DIAL_TO = 495.0

READOUT_X = DIAL_C[0] + DIAL_OUTER + DIAL_GAP
READOUT_W = W - READOUT_X - DIAL_GAP
READOUT_H = 38
READOUT_NOTE_H = 46


SCALE = 1.0


def px(offset):
    """Scale a 320x240-era pixel offset to the layout's current scale."""
    return int(offset * SCALE)


def resize(width, height):
    """Re-derive the layout in device pixels for a screen that is not 320x240."""
    global SCALE, W, H, HEADER_H, FOOTER_H, BODY_TOP, BODY_H, BODY_MID, PAD
    global DIAL_GAP, DIAL_OUTER, DIAL_INNER, DIAL_C, READOUT_X, READOUT_W
    global READOUT_H, READOUT_NOTE_H
    global SIZE_TITLE, SIZE_HUGE, SIZE_BIG, SIZE_LABEL, SIZE_VALUE, SIZE_SMALL

    SCALE = height / 240.0
    W, H = width, height
    HEADER_H, FOOTER_H = px(30), px(20)
    BODY_TOP = HEADER_H
    BODY_H = H - HEADER_H - FOOTER_H
    BODY_MID = BODY_TOP + BODY_H // 2
    PAD = px(10)

    DIAL_GAP, DIAL_OUTER, DIAL_INNER = px(16), px(82), px(62)
    DIAL_C = (DIAL_GAP + DIAL_OUTER, BODY_TOP + BODY_H // 2 + px(2))

    READOUT_X = DIAL_C[0] + DIAL_OUTER + DIAL_GAP
    READOUT_W = W - READOUT_X - DIAL_GAP
    READOUT_H, READOUT_NOTE_H = px(38), px(46)

    SIZE_TITLE, SIZE_HUGE, SIZE_BIG = px(19), px(44), px(26)
    SIZE_LABEL, SIZE_VALUE, SIZE_SMALL = px(12), px(17), px(11)


DIAL_TUCK = 0.09


def dial_span(centre=None, radius=None):
    """Return (top, bottom) for a column beside a dial."""
    centre = DIAL_C if centre is None else centre
    radius = DIAL_OUTER if radius is None else radius
    tuck = int(radius * DIAL_TUCK)
    return centre[1] - radius + tuck, centre[1] + radius - tuck


def readout_rows(count, height=READOUT_H):
    """Return the y at which each of `count` readout rows starts."""
    span_top, span_bottom = dial_span()
    room = BODY_TOP + BODY_H - px(6) - count * height
    top = max(BODY_TOP + px(6), min(span_top, room))
    if count > 1:
        step = max(height, (span_bottom - span_top) // count)
        if top + count * step <= BODY_TOP + BODY_H:
            return [top + index * step for index in range(count)]
    return [top + index * height for index in range(count)]


SIZE_TITLE = 19
SIZE_HUGE = 44
SIZE_BIG = 26
SIZE_LABEL = 12
SIZE_VALUE = 17
SIZE_SMALL = 11

DIALS = {
    1: {"centres": ((160, 125),), "outer": 74, "inner": 56,
        "value": SIZE_HUGE, "label": SIZE_VALUE},
    2: {"centres": ((85, 125), (235, 125)), "outer": 62, "inner": 46,
        "value": 34, "label": SIZE_LABEL},
    3: {"centres": ((60, 125), (160, 125), (260, 125)), "outer": 46, "inner": 34,
        "value": 26, "label": SIZE_SMALL},
    4: {"centres": ((85, 84), (235, 84), (85, 166), (235, 166)), "outer": 40,
        "inner": 29, "value": 22, "label": SIZE_SMALL},
}


RAMP_STEPS = 65

PALE_SUM = 384

STRIPE = 10


class Theme:
    """A palette's colours, plus the ramp a gauge fills with."""

    def __init__(self, name, bg, panel, ink, dim, accent, ramp, grid=None,
                 accent_b=None, image=None):
        self.name = name
        self.bg = color.rgb(*bg)
        self.panel = color.rgb(*panel)
        self.ink = color.rgb(*ink)
        self.dim = color.rgb(*dim)
        self.accent = color.rgb(*accent)
        self.accent_b = color.rgb(*accent_b) if accent_b else self.accent
        self.ramp = tuple((pos, color.rgb(*rgb).to_oklch()) for pos, rgb in ramp)
        self.grid = color.rgb(*grid) if grid else self.dim
        self.key = (name, tuple(bg), tuple(accent),
                    tuple(accent_b) if accent_b else tuple(accent),
                    tuple(ramp[0][1]), tuple(ramp[-1][1]))
        self.pale = sum(bg) >= PALE_SUM
        self.stripe = self.bg.darken(STRIPE) if self.pale else self.bg.lighten(STRIPE)
        self.steps = tuple(color.ramp(self.ramp, RAMP_STEPS))
        self.image = {count: tuple(color.rgb(*rgb) for rgb in greys)
                      for count, greys in (image or {}).items()}

    def at(self, fraction):
        """Return the ramp colour for a 0-1 value."""
        if fraction <= 0.0:
            return self.steps[0]
        if fraction >= 1.0:
            return self.steps[-1]
        return self.steps[int(fraction * (RAMP_STEPS - 1) + 0.5)]


THEMES = {
    "dark": Theme(
        "dark",
        bg=(18, 20, 28), panel=(26, 30, 43), ink=(242, 245, 255), dim=(139, 147, 171),
        accent=(56, 232, 209),
        ramp=((0.0, (56, 232, 209)), (0.45, (126, 211, 117)),
              (0.72, (236, 159, 7)), (1.0, (215, 25, 8))),
        grid=(44, 51, 70),
    ),
}

DEFAULT = "dark"


def get(name):
    return THEMES.get(name, THEMES[DEFAULT])


def from_palette(name, palette):
    """Build a theme from a host-sent palette, or return None if it is unusable."""
    if not isinstance(palette, dict):
        return None
    try:
        colours = {key: tuple(int(v) for v in palette[key][:3])
                   for key in ("bg", "panel", "ink", "dim", "accent")}
        for rgb in colours.values():
            if len(rgb) != 3:
                return None
        grid = palette.get("grid")
        second = palette.get("accent_b")
        ramp = tuple((float(pos), tuple(int(v) for v in rgb[:3]))
                     for pos, rgb in palette["ramp"])
        if not ramp:
            return None
        image = {len(greys): [tuple(int(v) for v in rgb[:3]) for rgb in greys]
                 for greys in (palette.get("image") or {}).values()}
        return Theme(name, ramp=ramp,
                     grid=tuple(int(v) for v in grid[:3]) if grid else None,
                     accent_b=tuple(int(v) for v in second[:3]) if second else None,
                     image=image, **colours)
    except (TypeError, ValueError, KeyError, IndexError):
        return None
