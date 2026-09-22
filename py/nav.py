"""Header touch chrome: one icon per mode, right-aligned."""

import draw
import look
import ui

CONTENT = "content"
MACROS = "macros"
SETTINGS = "settings"

ICONS = ((MACROS, "\ue312"), (SETTINGS, "\ue8b8"))

ICON_CHARS = "".join(icon for _, icon in ICONS)
ICON_FONT = "symbols"


def boxes():
    """Return the tap target rect for each mode."""
    size = look.HEADER_H
    out = {}
    for i, (name, _) in enumerate(reversed(ICONS)):
        out[name] = (look.W - ui.MARGIN() - (i + 1) * size, 0,
                     size, size)
    return out


def hit(x, y):
    for name, (bx, by, bw, bh) in boxes().items():
        if bx <= x < bx + bw and by <= y < by + bh:
            return name
    return None


def render(theme, mode):
    size = look.px(20)
    rule = max(1, look.HEADER_H // 15)
    spots = boxes()
    for name, icon in ICONS:
        bx, by, bw, bh = spots[name]
        lit = (name == mode)
        if lit:
            screen.pen = theme.bg
            screen.shape(shape.rounded_rectangle(
                rect(bx + look.px(3), by + look.px(3),
                     bw - look.px(6), bh - look.px(6) - rule), ui.CORNER()))
        width = draw.text_width(icon, size, ICON_FONT)
        draw.blit_label(icon, size, theme.accent if lit else theme.dim,
                        bx + (bw - width) // 2,
                        draw.centre_y(size, (bh - rule) // 2, draw.ICON_CENTRE),
                        name=ICON_FONT)
