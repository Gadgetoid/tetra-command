"""The clock faces: four analogue dials and two digital ones."""

import machine
import math
import time

import draw
import look
import pages

WEATHER_FONT = "weather"
ICON_SIZE = look.px(32)

# Past this the reading is drawn with its age instead of the accent.
STALE_S = 3600


def _place(here, theme):
    """Return the place label and the pen it is drawn in, aged if it is stale."""
    if not here:
        return None, theme.accent
    label = here.get("place")
    at = here.get("at")
    if at is None:
        return label, theme.accent
    age = time.time() - at
    if age < STALE_S:
        return label, theme.accent
    old = draw.ago(age)
    return ("%s  %s" % (label, old) if label else old), theme.dim


def _high_low(weather):
    """Format the day's range as "H 24 L 12", or None."""
    unit = weather.get("temp_unit") or ""
    parts = []
    for mark, key in (("H", "high"), ("L", "low")):
        value = weather.get(key)
        if value is not None:
            parts.append(f"{mark} {value:.0f}\u00b0{unit}")
    return "   ".join(parts) or None

LCD_FONT = "lcd"
LCD_FILE = "lcd.af"

DIGITS_FONT = "digits"
DIGITS_FILE = "digits.af"

CENTRE = look.DIAL_C
RADIUS = look.DIAL_OUTER

#   plate          "disc", "squircle", or None for the background
#   marks_style    "bars", "dots", or "ovals"
#   hands_style    "bars", or "ovals"
#   band           where the marks reach, as a fraction of RADIUS
#   hub            pivot disc radius in pixels, or 0 for none
#   *_mark         (length, half-width), as fractions of RADIUS
#   *_hand         (length, half-width, tail), as fractions of RADIUS
#   sec_ring       (how far along the second hand, outer radius, band), or None
#   sweep          None to sweep the minute, or the seconds a revolution takes
FACES = {
    "railway": {
        "label": "Railway",
        "face": (245, 245, 242), "marks": (16, 16, 18),
        "hands": (222, 32, 28), "second": (24, 24, 26),
        "plate": "disc", "marks_style": "bars", "hands_style": "bars", "star": False,
        "band": 0.97,
        "hour_mark": (0.19, 0.055), "min_mark": (0.095, 0.019),
        "hour_hand": (0.55, 0.062, 0.13), "min_hand": (0.86, 0.048, 0.13),
        "sec_hand": (0.76, 0.011, 0.13), "hub": 4,
        "sec_ring": None, "sweep": None,
    },
    "dots": {
        "label": "Dots",
        "face": (250, 250, 248), "marks": (18, 18, 20),
        "hands": (18, 18, 20), "second": (18, 18, 20),
        "plate": "disc", "marks_style": "dots", "hands_style": "bars", "star": True,
        "band": 0.97,
        "hour_mark": (0.0, 0.042), "min_mark": (0.0, 0.017),
        "hour_hand": (0.52, 0.019, 0.24), "min_hand": (0.88, 0.015, 0.24),
        "sec_hand": (0.88, 0.009, 0.24), "hub": 7,
        "sec_ring": None, "sweep": None,
    },
    "squircle": {
        "label": "Squircle",
        "face": None, "marks": None,
        "hands": None, "second": None,
        "plate": "squircle", "marks_style": "bars", "hands_style": "bars", "star": False,
        "band": 0.97,
        "hour_mark": (0.16, 0.030), "min_mark": (0.06, 0.012),
        "hour_hand": (0.52, 0.040, 0.16), "min_hand": (0.84, 0.030, 0.16),
        "sec_hand": (0.80, 0.010, 0.16), "hub": 5,
        "sec_ring": None, "sweep": None,
    },
    "amsterdam": {
        "label": "Amsterdam",
        "face": (228, 228, 230), "marks": (59, 76, 145),
        "hands": (43, 48, 90), "second": (155, 50, 65),
        "plate": "disc", "marks_style": "ovals", "hands_style": "ovals", "star": False,
        "band": 0.906,
        "hour_mark": (0.277, 0.044), "min_mark": (0.0, 0.022),
        "hour_hand": (0.537, 0.054, 0.163), "min_hand": (0.850, 0.040, 0.234),
        "sec_hand": (0.920, 0.019, 0.341), "hub": 3,
        "sec_ring": (0.572, 0.085, 0.022), "sweep": 57.0,
    },
}
DEFAULT_FACE = "railway"

DIGITAL = {
    "digital": {"label": "Digital", "font": DIGITS_FONT, "file": DIGITS_FILE,
                "ghost": None, "colon": "dots"},
    "lcd": {"label": "Digital LCD", "font": LCD_FONT, "file": LCD_FILE,
            "ghost": "88", "colon": "glyph"},
}

_face_cache = {}
_hands_cache = {}
_baked_for = None


def _colours(spec, theme, themed):
    """Return the face's own livery, or the page theme's where it has none."""
    return {
        "face": color.rgb(*spec["face"]) if spec["face"] and not themed else theme.panel,
        "marks": color.rgb(*spec["marks"]) if spec["marks"] and not themed else theme.dim,
        "hands": color.rgb(*spec["hands"]) if spec["hands"] and not themed else theme.ink,
        "second": (color.rgb(*spec["second"]) if spec["second"] and not themed
                   else theme.accent),
    }


def _bar(inner, outer, half_width):
    """Return a blunt-ended bar pointing at twelve, from the origin."""
    return shape.rectangle(rect(-half_width, -outer, half_width * 2.0, outer - inner))


def _aim(bar, centre, degrees):
    """Point a bar at a clock angle."""
    bar.transform = mat3().translate(centre[0], centre[1]).rotate(degrees)
    return bar


def _oval(inner, outer, half_width):
    """Return a round-ended bar pointing at twelve, from the origin."""
    return shape.rounded_rectangle(
        rect(-half_width, -outer, half_width * 2.0, outer - inner), half_width)


def _dot(radius_at, size):
    """Return a dot on the minute track, at twelve."""
    return shape.circle(vec2(0, -radius_at), size)


def _ring(radius_at, outer, band):
    """Return a ring around a point on a hand, at twelve."""
    return shape.arc(vec2(0, -radius_at), outer - band, outer, 0, 360)


def _bake_face(spec, pens):
    """Bake the dial for one face."""
    size = RADIUS * 2 + 4
    face = image(size, size)
    face.antialias = image.X4
    face.pen = brush.erase()
    face.rectangle(rect(0, 0, size, size))

    middle = (size / 2.0, size / 2.0)
    face.pen = pens["face"]
    if spec["plate"] == "squircle":
        face.shape(shape.squircle(vec2(*middle), RADIUS, 4))
    elif spec["plate"] == "disc":
        face.shape(shape.circle(vec2(*middle), RADIUS))

    face.pen = pens["marks"]
    band = RADIUS * spec["band"]
    hour_len, hour_half = spec["hour_mark"]
    min_len, min_half = spec["min_mark"]
    if spec["marks_style"] == "dots":
        track = RADIUS * 0.85
        big, small = _dot(track, RADIUS * hour_half), _dot(track, RADIUS * min_half)
        for tick in range(60):
            face.shape(_aim(big if tick % 5 == 0 else small, middle, tick * 6.0))
    elif spec["marks_style"] == "ovals":
        hour_mark = _oval(RADIUS * (1.0 - hour_len), band, RADIUS * hour_half)
        minute_dot = _dot(band - RADIUS * min_half, RADIUS * min_half)
        for tick in range(60):
            face.shape(_aim(hour_mark if tick % 5 == 0 else minute_dot, middle,
                            tick * 6.0))
    else:
        hour_mark = _bar(RADIUS * (1.0 - hour_len), band, RADIUS * hour_half)
        minute_mark = _bar(RADIUS * (1.0 - min_len), band, RADIUS * min_half)
        for tick in range(60):
            face.shape(_aim(hour_mark if tick % 5 == 0 else minute_mark, middle,
                            tick * 6.0))

    return face


def _bake_hands(spec):
    """Return each hand as the shapes that draw it."""
    oval = spec["hands_style"] == "ovals"
    bar = _oval if oval else _bar

    hands = []
    for length, half, back in (spec["hour_hand"], spec["min_hand"]):
        tail, outer, wide = -RADIUS * back, RADIUS * length, RADIUS * half
        parts = [bar(tail, outer, wide)]
        if oval:
            parts.append(_bar(tail, tail + wide, wide))
        hands.append(parts)

    length, half, back = spec["sec_hand"]
    tail, outer, wide = -RADIUS * back, RADIUS * length, RADIUS * half
    if spec["sec_ring"]:
        at, ring_outer, band = spec["sec_ring"]
        middle, hole = outer * at, RADIUS * (ring_outer - band)
        second = [bar(tail, middle - hole, wide), bar(middle + hole, outer, wide),
                  _ring(middle, RADIUS * ring_outer, RADIUS * band)]
    else:
        second = [bar(tail, outer, wide)]
    hands.append(second)
    return tuple(tuple(parts) for parts in hands)


def _face(name, theme, themed):
    """Return (spec, pens, dial, hands), baking on first use."""
    global _baked_for
    if _baked_for != theme.key:
        _face_cache.clear()
        _hands_cache.clear()
        _baked_for = theme.key
    spec = FACES.get(name) or FACES[DEFAULT_FACE]
    pens = _colours(spec, theme, themed)
    key = (spec["label"], themed)
    if key not in _face_cache:
        _face_cache[key] = _bake_face(spec, pens)
        _hands_cache[key] = _bake_hands(spec)
    return spec, pens, _face_cache[key], _hands_cache[key]


def _hand(parts, degrees, pen):
    screen.pen = pen
    for part in parts:
        screen.shape(_aim(part, CENTRE, degrees))


STEP_RIPPLE = 0.6
TWO_PI = math.pi * 2.0

SPRING_MS = 260

_spring_tween = None
_spring_over = None


def _spring(phase_ms, over_ms):
    """Return how far the hour and minute hands have closed on the new minute, 0 to 1."""
    global _spring_tween, _spring_over
    if _spring_over != over_ms:
        _spring_tween = tween(0.0, 1.0, over_ms, tween.CUBIC_OUT)
        _spring_over = over_ms
    return _spring_tween.at(phase_ms)


def _step(fraction):
    """Return how far a second hand is through one step, 0 to 1."""
    return fraction - STEP_RIPPLE / TWO_PI * math.sin(TWO_PI * fraction)


def _angles(hour, minute, second, sweep):
    """Return the degrees clockwise from twelve for the hour, minute and second hands."""
    if sweep is None:
        return ((hour % 12) * 30.0 + minute * 0.5, minute * 6.0 + second * 0.1,
                second * 6.0)

    behind = 1.0 - _spring(second * 1000.0, SPRING_MS)
    hours = (hour % 12) * 30.0 + minute * 0.5 - behind * 0.5
    minutes = minute * 6.0 - behind * 6.0

    step_s = sweep / 60.0
    steps = second / step_s
    if steps >= 60.0:
        return hours, minutes, 0.0
    taken = int(steps)
    return hours, minutes, (taken + _step(steps - taken)) * 6.0


def _register_font():
    """Load the weather icon font."""
    here = globals().get("__file__") or ""
    beside = here.rsplit("/", 1)[0] + "/icons.af" if "/" in here else "icons.af"
    draw.add_font(WEATHER_FONT, beside)


WIDEST_TIME = "44:44"
BLANK_TIME = "  :  "
BLANK_MINUTES = BLANK_TIME.partition(":")[2]

COLON_W, COLON_DOT = 0.20, 0.061
COLON_AT = (0.309, 0.720)

COLON_DIM = 90


def _colon_alpha():
    lit = 0.5 + 0.5 * math.cos(_local_time()[2] % 1.0 * math.pi * 2.0)
    return int(COLON_DIM + (255 - COLON_DIM) * lit)


def _digits_font(spec):
    """Return the font name for a digital face, loading it on first use."""
    wanted = spec["font"]
    if not draw.has_font(wanted):
        here = globals().get("__file__") or ""
        beside = (here.rsplit("/", 1)[0] + "/" + spec["file"] if "/" in here
                  else spec["file"])
        draw.add_font(wanted, beside)
    return wanted if draw.has_font(wanted) else draw.TEXT


def _digital(clock, weather, label, label_pen, theme, spec):
    """Draw the band with no dial, laid out as a desk clock."""
    left, right = look.PAD + look.px(2), look.W - look.PAD - look.px(2)
    top = look.BODY_TOP + look.px(6)

    if clock.get("date"):
        draw.blit_label(clock["date"], look.SIZE_VALUE, theme.dim, left, top)
    if label:
        draw.blit_label(label, look.SIZE_VALUE, label_pen, right, top, align=2)

    text = clock.get("time") or BLANK_TIME
    hours, _, minutes = text.partition(":")
    gap = look.px(8)
    digits_top = look.BODY_TOP + look.px(26)
    room = (look.BODY_TOP + look.BODY_H - look.px(38)) - digits_top
    name = _digits_font(spec)
    cap = draw.cap_of(name)
    size = int(room / cap)
    dots = spec["colon"] == "dots"
    span = right - left
    widest = draw.text_width(WIDEST_TIME, size, name) + gap * 2
    if dots:
        widest += int(size * draw.CAP * COLON_W) - draw.text_width(":", size, name)
    if widest > span:
        size = int(size * span / widest)
    left_w = draw.text_width(hours, size, name)
    right_w = draw.text_width(minutes or BLANK_MINUTES, size, name)
    ink = int(size * cap)
    colon_w = int(ink * COLON_W) if dots else draw.text_width(":", size, name)
    x = left
    minutes_x = right - right_w
    y = digits_top + (room - ink) // 2 - (size - ink)
    ghosting = spec["ghost"] and name == spec["font"]
    if ghosting:
        draw.blit_label(spec["ghost"], size, theme.grid, x, y, name=name)
        draw.blit_label(spec["ghost"], size, theme.grid, minutes_x, y, name=name)
    draw.blit_label(hours, size, theme.ink, x, y, name=name)
    draw.blit_label(minutes or BLANK_MINUTES, size, theme.ink, minutes_x, y, name=name)
    colon_x = (x + left_w + minutes_x) / 2.0
    if dots:
        ink_top = y + size - ink
        screen.pen = theme.accent
        screen.alpha = _colon_alpha()
        for at in COLON_AT:
            screen.shape(shape.circle(vec2(colon_x, ink_top + ink * at), ink * COLON_DOT))
    else:
        colon_left = colon_x - colon_w / 2.0
        if ghosting:
            draw.blit_label(":", size, theme.grid, colon_left, y, name=name)
        screen.alpha = _colon_alpha()
        draw.blit_label(":", size, theme.accent, colon_left, y, name=name)
    screen.alpha = 255

    y = look.BODY_TOP + look.BODY_H - look.px(34)
    x = left
    icon = weather.get("icon")
    if icon:
        drawn = draw.blit_label(icon, ICON_SIZE, theme.ink, x,
                                draw.icon_baseline(y, look.SIZE_BIG, ICON_SIZE),
                                name=WEATHER_FONT)
        x += (drawn or 0) + 8
    if weather.get("temp") is not None:
        unit = weather.get("temp_unit") or ""
        x += draw.blit_label("{:.0f}\u00b0{}".format(weather["temp"], unit),
                             look.SIZE_BIG, theme.ink, x, y) + 12
    span = _high_low(weather)
    if weather.get("condition"):
        draw.blit_label(weather["condition"], look.SIZE_SMALL, theme.dim, x,
                        y + (2 if span else 10))
    if span:
        draw.blit_label(span, look.SIZE_SMALL, theme.dim, x,
                        y + (look.SIZE_SMALL + 6 if weather.get("condition") else 10))
    if weather.get("wind") is not None:
        draw.blit_label("wind {:.0f} {}".format(weather["wind"],
                                                weather.get("wind_unit") or ""),
                        look.SIZE_SMALL, theme.dim, right, y + 10, align=2)
    if not weather:
        draw.blit_label("no location set", look.SIZE_SMALL, theme.dim, right, y + 10,
                        align=2)


def render(page, frame, _history, theme):
    host = frame.get("clock") or {}
    here = (frame.get("places") or {}).get((page or {}).get("id"))
    clock = here if (here or {}).get("hour") is not None else host
    weather = here or frame.get("weather") or {}
    label, label_pen = _place(here, theme)

    _register_font()
    chosen = ((page or {}).get("face") or DEFAULT_FACE)
    if chosen in DIGITAL:
        _resync(host, frame.get("seq"))
        _digital(clock, weather, label, label_pen, theme, DIGITAL[chosen])
        return

    spec, pens, dial, hands = _face(chosen, theme, bool((page or {}).get("themed")))
    size = dial.width
    screen.blit(dial, vec2(int(CENTRE[0] - size / 2), int(CENTRE[1] - size / 2)))

    if clock.get("hour") is None:
        draw.blit_label("no time", look.SIZE_VALUE, theme.dim,
                        CENTRE[0], CENTRE[1] - look.px(8), align=1)
    else:
        _resync(host, frame.get("seq"))
        hour, minute, second = _local_time(_zone_offset(host, here))
        hour_hand, minute_hand, second_hand = hands
        hours, minutes, seconds = _angles(hour, minute, second, spec["sweep"])
        _hand(hour_hand, hours, pens["hands"])
        _hand(minute_hand, minutes, pens["hands"])
        _hand(second_hand, seconds, pens["second"])
        if spec["hub"]:
            screen.pen = pens["second"]
            screen.shape(shape.circle(vec2(*CENTRE), look.px(spec["hub"])))

    x = look.READOUT_X
    span_top, span_bottom = draw.dial_span(CENTRE, RADIUS)
    draw.column_lines((
        (clock.get("time"), look.SIZE_BIG, theme.ink),
        (label, look.SIZE_SMALL, label_pen),
        (clock.get("date"), look.SIZE_SMALL, theme.dim),
    ), top=int(span_top - look.SIZE_BIG * (1.0 - draw.cap_of())))

    icon = weather.get("icon")
    span = _high_low(weather)
    wind = None
    if weather.get("wind") is not None:
        wind = "wind {:.0f} {}".format(weather["wind"], weather.get("wind_unit") or "")
    elif not weather:
        wind = "no location set"

    rows = []
    if weather.get("temp") is not None or icon:
        rows.append(("weather", look.SIZE_BIG))
    for text_value in (span, weather.get("condition"), wind):
        if text_value:
            rows.append((text_value, look.SIZE_SMALL))

    if rows:
        baselines = [0] * len(rows)
        baselines[-1] = int(span_bottom)
        for i in range(len(rows) - 2, -1, -1):
            baselines[i] = baselines[i + 1] - draw.step(rows[i][1],
                                                        rows[i + 1][1])
        for (text_value, size), baseline in zip(rows, baselines):
            y = baseline - size
            if text_value == "weather":
                drawn = draw.blit_label(icon or "", ICON_SIZE, theme.ink, x,
                                        draw.icon_baseline(y, size, ICON_SIZE),
                                        name=WEATHER_FONT)
                if weather.get("temp") is not None:
                    unit = weather.get("temp_unit") or ""
                    draw.blit_label("{:.0f}\u00b0{}".format(weather["temp"], unit),
                                    size, theme.ink,
                                    x + (drawn + look.px(8) if drawn else 0), y)
            else:
                draw.blit_label(text_value, size, theme.dim, x, y)


RESYNC_S = 30

_synced = False
_synced_seq = None

_phase_second = None
_phase_at = 0


def _zone_offset(host, there):
    """Return the seconds between the host's local time and the location a page shows."""
    if not host or not there or there.get("hour") is None or host.get("hour") is None:
        return 0
    theirs = there["hour"] * 3600 + there["minute"] * 60 + there.get("seconds", 0)
    ours = host["hour"] * 3600 + host["minute"] * 60 + host.get("seconds", 0)
    return (theirs - ours + 43200) % 86400 - 43200


def _local_time(offset=0):
    """Return the hour, minute and fractional second off the hardware clock."""
    global _phase_second, _phase_at
    parts = time.localtime()
    whole = parts[5]
    now = time.ticks_ms()
    if whole != _phase_second:
        _phase_second = whole
        _phase_at = now
    fraction = min(1.0, time.ticks_diff(now, _phase_at) / 1000.0)
    at = (parts[3] * 3600 + parts[4] * 60 + whole + offset) % 86400
    return at // 3600, (at % 3600) // 60, at % 60 + fraction


def _resync(clock, seq=None):
    """Set the clock from the host's, on the first reading and past RESYNC_S of drift."""
    global _synced, _synced_seq
    if _synced and seq == _synced_seq:
        return
    _synced_seq = seq
    hour = clock.get("hour")
    minute = clock.get("minute")
    second = clock.get("seconds")
    if hour is None or minute is None or second is None:
        return
    parts = time.localtime()
    theirs = hour * 3600 + minute * 60 + second
    ours = parts[3] * 3600 + parts[4] * 60 + parts[5]
    drift = (theirs - ours + 43200) % 86400 - 43200
    if _synced and -RESYNC_S <= drift <= RESYNC_S:
        return
    machine.RTC().datetime((parts[0], parts[1], parts[2], parts[6],
                            hour, minute, second, 0))
    _synced = True


pages.EXTRA["clockface"] = render
pages.ANIMATED.add("clockface")
