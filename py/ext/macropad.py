"""A macro pad page: squircle keys with Material Symbols icons, from macros_config.py."""

import draw
import look
import pages

from macros_config import BUTTONS, COLS, ROWS

ICON_FONT = "symbols"

N_IDLE, N_DOWN = 4.0, 7.0

FLASH_MS = 140

_keys = []
_built_for = None
_lit = None
_lit_until = 0
_modal = None


def _grid(entries, top, height, cols, rows, theme):
    """Bake a shape and two gradients per cell, laid out in the given band."""
    gap = look.px(10)
    room_w = look.W - gap * (cols + 1)
    kw, kh = room_w // cols, (height - gap * (rows + 1)) // rows
    out = []
    for i, spec in enumerate(entries[:cols * rows]):
        col, row = i % cols, i // cols
        x = gap + col * (kw + gap)
        y = top + gap + row * (kh + gap)
        cx, cy = x + kw / 2.0, y + kh / 2.0
        size = min(kw, kh) / 2.0
        out.append({
            "spec": spec,
            "box": (x, y, kw, kh),
            "idle": shape.squircle(vec2(cx, cy), size, N_IDLE),
            "down": shape.squircle(vec2(cx, cy), size, N_DOWN),
            "face": brush.gradient(brush.LINEAR, cx, cy - size, cx, cy + size,
                                   ((0.0, theme.panel), (1.0, theme.bg))),
            "lit": brush.gradient(brush.LINEAR, cx, cy - size, cx, cy + size,
                                  ((0.0, theme.accent), (1.0, theme.accent_b))),
            "centre": (cx, cy),
            "size": size,
        })
    return out


def _build(theme):
    global _keys, _built_for
    _keys = _grid(BUTTONS, look.BODY_TOP, look.BODY_H, COLS, ROWS, theme)
    _built_for = (theme.key, look.W, look.H, len(BUTTONS))


def _under(keys, x, y):
    for i, key in enumerate(keys):
        kx, ky, kw, kh = key["box"]
        if kx <= x < kx + kw and ky <= y < ky + kh:
            return i
    return None


def on_down(x, y, now_ms, theme):
    """Handle a finger landing and return (macro, is_hold), or (None, False)."""
    global _lit, _lit_until
    if _modal is not None:
        return None, False
    index = _under(_keys, x, y)
    if index is None:
        return None, False
    spec = _keys[index]["spec"]
    if spec.get("hold"):
        _lit, _lit_until = index, now_ms + 10 ** 9
        return spec["hold"], True
    return None, False


def on_tap(x, y, now_ms, theme):
    """Handle a finger lifting without a swipe and return a macro to run, or None."""
    global _lit, _lit_until, _modal

    if _modal is not None:
        parent, options = _modal
        index = _under(options, x, y)
        _modal = None
        if index is None:
            return None
        _lit, _lit_until = parent, now_ms + FLASH_MS
        return options[index]["spec"].get("macro")

    index = _under(_keys, x, y)
    if index is None:
        return None
    spec = _keys[index]["spec"]
    if spec.get("hold"):
        return None
    if spec.get("modal"):
        _modal = (index, _grid(spec["modal"], look.BODY_TOP + look.BODY_H // 4,
                               look.BODY_H // 2, len(spec["modal"]), 1, theme))
        return None
    _lit, _lit_until = index, now_ms + FLASH_MS
    return spec.get("macro")


def on_release(now_ms):
    """End the flash on a held key that was let go."""
    global _lit, _lit_until
    if _lit is not None and _lit_until > now_ms + FLASH_MS:
        _lit_until = now_ms + FLASH_MS


def close_modal():
    global _modal
    _modal = None


def _draw_keys(keys, theme, lit_index, icon_size, label_size):
    for i, key in enumerate(keys):
        down = (i == lit_index)
        screen.pen = key["lit"] if down else key["face"]
        screen.shape(key["down"] if down else key["idle"])

        cx, cy = key["centre"]
        spec = key["spec"]
        icon = spec.get("icon")
        if icon and draw.has_font(ICON_FONT):
            w = draw.text_width(icon, icon_size, ICON_FONT)
            draw.blit_label(icon, icon_size, theme.bg if down else theme.ink,
                            cx - w // 2, cy - icon_size, name=ICON_FONT)
        label = spec.get("label")
        if label:
            draw.blit_label(label, label_size, theme.bg if down else theme.dim,
                            cx, cy + look.px(16), align=1)


def render(page, frame, _history, theme):
    if _built_for != (theme.key, look.W, look.H, len(BUTTONS)):
        _build(theme)

    now = frame.get("ticks", 0)
    lit = _lit if now < _lit_until else None
    icon_size, label_size = look.px(30), look.SIZE_SMALL

    _draw_keys(_keys, theme, None if _modal else lit, icon_size, label_size)

    if _modal is not None:
        screen.pen = theme.bg
        screen.alpha = 200
        screen.rectangle(rect(0, look.BODY_TOP, look.W, look.BODY_H))
        screen.alpha = 255
        parent, options = _modal
        draw.blit_label(_keys[parent]["spec"].get("label", ""), look.SIZE_VALUE,
                        theme.dim, look.W // 2,
                        look.BODY_TOP + look.BODY_H // 4 - look.px(22), align=1)
        _draw_keys(options, theme, None, icon_size, label_size)


pages.EXTRA["macropad"] = render
pages.ANIMATED.add("macropad")
