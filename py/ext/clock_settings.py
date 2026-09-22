"""Pick which clock face the clock page draws, and whose colours it uses."""

import clockface
import config
import draw
import look
import pages
import ui

N_IDLE = 4.0

DIGIT_GAP = 0.12

DIGIT_INK = 0.95

_layout = None
_built_for = None
_changed = False


def faces():
    out = []
    for name, spec in clockface.FACES.items():
        out.append((name, spec.get("label") or name, spec, False))
    for name, spec in clockface.DIGITAL.items():
        out.append((name, spec.get("label") or name, spec, True))
    return out


def take_change():
    global _changed
    was, _changed = _changed, False
    return was


def _bake(spec, pens, radius):
    was = clockface.RADIUS
    clockface.RADIUS = radius
    try:
        return clockface._bake_face(spec, pens), clockface._bake_hands(spec)
    finally:
        clockface.RADIUS = was


def _build(theme):
    global _layout, _built_for

    entries = faces()
    themed = bool(config.get("clock_themed"))

    left, top, right, bottom = ui.frame()
    cols = len(entries)
    rows = 1
    col_w, x_of = ui.columns(cols, ui.GAP(), left, right)

    tiles_top = top
    switch_block = ui.GAP() + ui.SWITCH_H()
    room = bottom - tiles_top - switch_block - ui.GAP()
    per_row = (room - ui.GAP() * (rows - 1)) // rows
    tile = min(col_w, per_row - ui.CAPTION_BAND())
    per_row = tile + ui.CAPTION_BAND()
    radius = int(tile / 2.0 - look.px(6))

    keys = []
    for i, (name, label, spec, digital) in enumerate(entries):
        col, row = i % cols, i // cols
        x = x_of(col) + (col_w - tile) // 2
        y = tiles_top + row * (per_row + ui.GAP())
        key = {
            "face": name, "label": label, "spec": spec, "digital": digital,
            "box": (x, y, tile, tile),
            "shape": shape.squircle(vec2(x + tile / 2.0, y + tile / 2.0),
                                    tile / 2.0, N_IDLE),
            "centre": (x + tile / 2.0, y + tile / 2.0),
            "radius": radius,
            "label_x": x_of(col) + col_w // 2,
            "label_y": draw.centre_y(ui.CAPTION_FITTED(),
                                     y + tile + ui.CAPTION_BAND() // 2),
        }
        if not digital:
            pens = clockface._colours(spec, theme, themed)
            if spec.get("face") is None or themed:
                pens = dict(pens)
                pens["face"] = theme.bg
            key["pens"] = pens
            key["dial"], key["hands"] = _bake(spec, pens, radius)
        keys.append(key)

    switch_top = tiles_top + rows * (per_row + ui.GAP())
    switch_h = ui.SWITCH_H()
    switch_w = int(switch_h * 1.8)
    caption = "Use theme colours"
    caption_w = draw.text_width(caption, ui.CONTROL())
    switch_x = left + caption_w + ui.GAP()
    inset = max(2, look.px(2))
    travel = switch_w - switch_h

    switch = {
        "caption": caption,
        "box": (left, switch_top, switch_x + switch_w - left, switch_h),
        "track": shape.rounded_rectangle(
            rect(switch_x, switch_top, switch_w, switch_h), switch_h // 2),
        "off": shape.circle(
            vec2(switch_x + switch_h / 2.0, switch_top + switch_h / 2.0),
            switch_h / 2.0 - inset),
        "on": shape.circle(
            vec2(switch_x + travel + switch_h / 2.0,
                 switch_top + switch_h / 2.0),
            switch_h / 2.0 - inset),
        "caption_y": draw.centre_y(ui.CONTROL(),
                                   switch_top + switch_h // 2),
    }

    _layout = {"keys": keys, "switch": switch}
    _built_for = _signature(theme)


def _signature(theme):
    return (theme.key, look.W, look.H, bool(config.get("clock_themed")))


def _hit(entries, x, y):
    for entry in entries:
        bx, by, bw, bh = entry["box"]
        if bx <= x < bx + bw and by <= y < by + bh:
            return entry
    return None


def on_down(x, y, theme):
    return False


def on_move(x, y):
    return


def on_release():
    return


def on_tap(x, y):
    global _changed
    if _built_for is None:
        return
    key = _hit(_layout["keys"], x, y)
    if key:
        _changed |= config.put("face", key["face"])
        return
    bx, by, bw, bh = _layout["switch"]["box"]
    if bx <= x < bx + bw and by <= y < by + bh:
        _changed |= config.put("clock_themed",
                               not bool(config.get("clock_themed")))


def _digital_preview(key, theme, selected, hour, minute):
    """Draw hours and minutes as separate strings over their ghost."""
    spec = key["spec"]
    name = spec["font"] if draw.has_font(spec["font"]) else draw.TEXT
    hours = "%02d" % hour
    minutes = "%02d" % minute
    room = key["radius"] * 2.0

    size = int(key["radius"] * DIGIT_INK / draw.CAP)
    size = draw.fit_size(hours + ":" + minutes, size, room, name)
    left_w = draw.text_width(hours, size, name)
    right_w = draw.text_width(minutes, size, name)
    colon_w = draw.text_width(":", size, name)
    gap = int(size * DIGIT_GAP)

    total = left_w + gap + colon_w + gap + right_w
    x = int(key["centre"][0] - total / 2.0)
    y = draw.centre_y(size, key["centre"][1])
    minutes_x = x + left_w + gap + colon_w + gap
    colon_x = x + left_w + gap

    ink = theme.bg if selected else theme.ink
    faint = theme.dim if selected else theme.grid
    if spec["ghost"] and name == spec["font"]:
        draw.blit_label(spec["ghost"], size, faint, x, y, name=name)
        draw.blit_label(spec["ghost"], size, faint, minutes_x, y, name=name)
        draw.blit_label(":", size, faint, colon_x, y, name=name)
    draw.blit_label(hours, size, ink, x, y, name=name)
    draw.blit_label(minutes, size, ink, minutes_x, y, name=name)
    draw.blit_label(":", size, theme.bg if selected else theme.accent,
                    colon_x, y, name=name)


def _preview(key, theme, selected, hour, minute, second):
    cx, cy = key["centre"]

    if key["digital"]:
        _digital_preview(key, theme, selected, hour, minute)
        return

    dial = key["dial"]
    size = dial.width
    screen.blit(dial, vec2(int(cx - size / 2), int(cy - size / 2)))

    hour_hand, minute_hand, second_hand = key["hands"]
    pens = key["pens"]
    hours, minutes, seconds = clockface._angles(hour, minute, second,
                                                key["spec"]["sweep"])
    for parts, degrees, pen in ((hour_hand, hours, pens["hands"]),
                                (minute_hand, minutes, pens["hands"]),
                                (second_hand, seconds, pens["second"])):
        screen.pen = pen
        for part in parts:
            screen.shape(clockface._aim(part, (cx, cy), degrees))

    hub = key["spec"].get("hub")
    if hub:
        screen.pen = pens["second"]
        screen.shape(shape.circle(vec2(cx, cy),
                                  max(1.0, hub * key["radius"] / 82.0)))


def render(page, frame, _history, theme):
    if _built_for != _signature(theme):
        _build(theme)

    hour, minute, second = clockface._local_time()

    chosen = config.get("face")
    for key in _layout["keys"]:
        on = key["face"] == chosen
        screen.pen = theme.accent if on else theme.panel
        screen.shape(key["shape"])
        _preview(key, theme, on, hour, minute, second)
        draw.blit_label(key["label"], ui.CAPTION_FITTED(),
                        theme.accent if on else theme.dim,
                        key["label_x"], key["label_y"], align=1)

    switch = _layout["switch"]
    left = ui.MARGIN()
    themed = bool(config.get("clock_themed"))
    draw.blit_label(switch["caption"], ui.CONTROL(), theme.dim, left,
                    switch["caption_y"])
    screen.pen = theme.accent if themed else theme.grid
    screen.shape(switch["track"])
    screen.pen = theme.bg if themed else theme.dim
    screen.shape(switch["on"] if themed else switch["off"])


pages.EXTRA["clock_settings"] = render
