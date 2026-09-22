"""A display settings page: brightness on a slider, colour temperature on icon keys, over DDC/CI."""

import ddc
import draw
import look
import pages
import ui

ICON_FONT = "symbols"

PRESETS = (
    (1, "sRGB", "\ue3b7"),
    (4, "5800", "\ue42e"),
    (5, "6500", "\ue430"),
    (6, "7500", "\ue1c6"),
    (8, "9300", "\ueb3b"),
)

BRIGHTNESS_ICON = "\ue518"

ICON_CHARS = BRIGHTNESS_ICON + "".join(icon for _, _, icon in PRESETS)

N_IDLE, N_DOWN = 4.0, 7.0

_layout = None
_built_for = None

_brightness = None
_brightness_max = 100
_preset = None
_dragging = False

PROBE_MS = 1500
_probe_at = None


def _read_state():
    global _brightness, _brightness_max, _preset
    current = ddc.get(ddc.BRIGHTNESS)
    if current is not None:
        _brightness, _brightness_max = current
    preset = ddc.get(ddc.COLOUR_PRESET)
    if preset is not None:
        _preset = preset[0]


def _probe(ticks):
    global _probe_at
    if _brightness is not None:
        return
    if _probe_at is not None and ticks - _probe_at < PROBE_MS:
        return
    _probe_at = ticks
    _read_state()


def _build(theme):
    global _layout, _built_for

    gap = ui.GAP()
    left, top, right, bottom = ui.frame()
    icon_size = look.px(26)

    track_h = look.px(14)
    knob_r = look.px(13)

    readout_w = draw.text_width("100%", ui.READOUT()) + gap
    track_x = left + icon_size + gap
    track_w = right - track_x - gap - readout_w
    track_y = top + ui.BAND()

    keys_title_top = track_y + track_h + ui.BAND()
    keys_top = keys_title_top + ui.BAND()

    count = len(PRESETS)
    kw, x_of = ui.columns(count, gap, left, right)
    kh = min(bottom - keys_top, kw)

    keys = []
    for i, (value, label, icon) in enumerate(PRESETS):
        x = x_of(i)
        y = keys_top
        cx, cy = x + kw / 2.0, y + kh / 2.0
        size = min(kw, kh) / 2.0
        keys.append({
            "value": value, "label": label, "icon": icon,
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

    _layout = {
        "title_y": draw.centre_y(ui.SECTION(), top + ui.BAND() // 2),
        "keys_title_y": draw.centre_y(ui.SECTION(),
                                      keys_title_top + ui.BAND() // 2),
        "icon_size": icon_size,
        "track": (track_x, track_y, track_w, track_h),
        "knob_r": knob_r,
        "readout_x": right,
        "fill": brush.gradient(brush.LINEAR, track_x, 0, track_x + track_w, 0,
                               ((0.0, theme.accent), (1.0, theme.accent_b))),
        "keys": keys,
    }
    _built_for = (theme.key, look.W, look.H)


def _value_at(x):
    track_x, _, track_w, _ = _layout["track"]
    if track_w <= 0:
        return 0
    fraction = (x - track_x) / float(track_w)
    fraction = 0.0 if fraction < 0.0 else (1.0 if fraction > 1.0 else fraction)
    return int(fraction * _brightness_max + 0.5)


def _on_track(x, y):
    track_x, track_y, track_w, track_h = _layout["track"]
    knob_r = _layout["knob_r"]
    if not (track_x - knob_r <= x <= track_x + track_w + knob_r):
        return False
    mid = track_y + track_h / 2.0
    return mid - knob_r * 2 <= y <= mid + knob_r * 2


def on_down(x, y, theme):
    global _dragging, _brightness
    if _built_for is None or not ddc.available():
        return False
    if _brightness is not None and _on_track(x, y):
        _dragging = True
        _brightness = _value_at(x)
        ddc.set(ddc.BRIGHTNESS, _brightness)
        return True
    return False


def on_move(x, y):
    global _brightness
    if not _dragging:
        return
    _brightness = _value_at(x)
    ddc.set(ddc.BRIGHTNESS, _brightness)


def on_release():
    global _dragging
    _dragging = False


def on_tap(x, y):
    global _preset
    if _built_for is None or not ddc.available():
        return
    for key in _layout["keys"]:
        kx, ky, kw, kh = key["box"]
        if kx <= x < kx + kw and ky <= y < ky + kh:
            _preset = key["value"]
            ddc.set(ddc.COLOUR_PRESET, _preset)
            return


def _draw_slider(theme):
    track_x, track_y, track_w, track_h = _layout["track"]
    knob_r = _layout["knob_r"]
    icon_size = _layout["icon_size"]
    radius = track_h // 2

    draw.blit_label("BRIGHTNESS", ui.SECTION(), theme.dim, ui.MARGIN(),
                    _layout["title_y"])

    mid_y = track_y + track_h // 2

    if draw.has_font(ICON_FONT):
        draw.blit_label(BRIGHTNESS_ICON, icon_size, theme.ink, ui.MARGIN(),
                        draw.centre_y(icon_size, mid_y, draw.ICON_CENTRE), name=ICON_FONT)

    screen.pen = theme.grid
    screen.shape(shape.rounded_rectangle(
        rect(track_x, track_y, track_w, track_h), radius))

    fraction = _brightness / float(_brightness_max) if _brightness_max else 0.0
    filled = int(track_w * fraction)
    if filled > 0:
        screen.pen = _layout["fill"]
        screen.shape(shape.rounded_rectangle(
            rect(track_x, track_y, max(filled, track_h), track_h), radius))

    knob_x = track_x + filled
    screen.pen = theme.ink
    screen.shape(shape.circle(vec2(knob_x, track_y + track_h / 2.0), knob_r))

    draw.blit_label("%d%%" % _brightness, ui.READOUT(), theme.ink,
                    _layout["readout_x"], draw.centre_y(ui.READOUT(), mid_y),
                    align=2)


def _draw_keys(theme):
    icon_size, label_size = look.px(28), ui.CAPTION_FITTED()
    for key in _layout["keys"]:
        selected = (key["value"] == _preset)
        screen.pen = key["lit"] if selected else key["face"]
        screen.shape(key["down"] if selected else key["idle"])

        cx, cy = key["centre"]
        kh = key["box"][3]
        if draw.has_font(ICON_FONT):
            w = draw.text_width(key["icon"], icon_size, ICON_FONT)
            draw.blit_label(key["icon"], icon_size,
                            theme.bg if selected else theme.ink, cx - w // 2,
                            draw.centre_y(icon_size, cy - kh // 8,
                                          draw.ICON_CENTRE), name=ICON_FONT)
        draw.blit_label(key["label"], label_size,
                        theme.bg if selected else theme.dim, cx,
                        draw.centre_y(label_size, cy + kh // 4), align=1)


def render(page, frame, _history, theme):
    global _built_for
    if _built_for != (theme.key, look.W, look.H):
        _build(theme)
    _probe(frame.get("ticks", 0))

    if not ddc.available() or _brightness is None:
        draw.blit_label("waiting for DDC/CI on this display", ui.CONTROL(),
                        theme.dim,
                        look.W // 2,
                        draw.centre_y(ui.CONTROL(), look.BODY_MID), align=1)
        return

    _draw_slider(theme)
    draw.blit_label("COLOUR TEMPERATURE", ui.SECTION(), theme.dim,
                    ui.MARGIN(), _layout["keys_title_y"])
    _draw_keys(theme)


pages.EXTRA["display"] = render
pages.ANIMATED.add("display")
