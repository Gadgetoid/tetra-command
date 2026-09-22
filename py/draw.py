"""Text, chrome and widget drawing over picovector."""

from array import array

import look

TEXT = "text"
ICON_NAME = "weather"
SYMBOLS = "symbols"

CAP_UNITS, ICON_UNITS, EM_UNITS = 81.0, 100.0, 128.0
CAP = CAP_UNITS / EM_UNITS
ICON_BOX = ICON_UNITS / EM_UNITS

ICON_CENTRE = ICON_BOX / 2.0

_caps = {}


def set_cap(name, ratio):
    _caps[name] = ratio


def cap_of(name=TEXT):
    return _caps.get(name, CAP)

GAP_RATIO = 0.75



_fonts = {}


def add_font(name, *paths, **options):
    """Load the first path that opens, passing `options` to font.load."""
    if name in _fonts:
        return True
    for path in paths:
        try:
            _fonts[name] = font.load(path, **options)
            return True
        except Exception:
            continue
    return False


def has_font(name):
    return name in _fonts


def text_width(text_value, size, name=TEXT):
    face = _fonts.get(name)
    if face is None:
        return 0
    was = screen.font
    screen.font = face
    try:
        measured = screen.measure_text(text_value, font_size=size)
    finally:
        if was is not None:
            screen.font = was
    return int(measured[0]) + 2


def blit_label(text_value, size, pen, x, y, align=0, name=TEXT):
    """Draw a string, aligned 0 left, 1 centre, 2 right about x, and return its width."""
    face = _fonts.get(name)
    if face is None or not text_value:
        return 0
    width = text_width(text_value, size, name)
    if align == 1:
        x -= width // 2
    elif align == 2:
        x -= width
    was = screen.font
    screen.font = face
    try:
        screen.pen = pen
        screen.text(text_value, vec2(int(x), int(y)), size)
    finally:
        if was is not None:
            screen.font = was
    return width


def centre_y(size, middle, centre=CAP / 2.0):
    return int(middle - size * (1.0 - centre))


def fit_size(text_value, size, width, name=TEXT):
    got = text_width(text_value, size, name)
    if not got or got <= width:
        return size
    return max(1, int(size * width / got))


def icon_baseline(text_y, text_size, icon_size):
    """Return where to draw an icon so it centres on the capitals of text at text_y."""
    return int(text_y + text_size * (1.0 - CAP / 2.0)
               - icon_size * (1.0 - ICON_CENTRE))


def gap_after(size, name=TEXT):
    """Return the whitespace a line of this size leaves under its baseline."""
    return int(size * cap_of(name) * GAP_RATIO)


def step(previous, size, name=TEXT):
    """Return the baseline-to-baseline step between two lines."""
    return gap_after(previous, name) + int(size * cap_of(name))


def dial_span(centre=None, radius=None):
    return look.dial_span(centre, radius)


def column_lines(entries, top=None, align=0):
    """Draw a stack of (text, size, pen) lines down the readout column and return the next y."""
    start = (look.BODY_TOP + look.px(12)) if top is None else top
    x = look.READOUT_X + (look.READOUT_W if align == 2 else 0)
    baseline, previous = None, None
    for text_value, size, pen in entries:
        if not text_value:
            continue
        if baseline is None:
            baseline = start + size
        else:
            baseline += step(previous, size)
        blit_label(text_value, size, pen, x, baseline - size, align=align)
        previous = size
    return start if baseline is None else baseline + gap_after(previous)


CURVE_STEPS = 2
SERIES_FLOOR = 20

_CLEARS = []


def clears(reset):
    """Register a reset to run on a theme change."""
    _CLEARS.append(reset)
    return reset


def clear_cache():
    for reset in _CLEARS:
        reset()


_weights = {}

def _basis(steps):
    """Return the Catmull-Rom weights for each fraction of a span."""
    table = _weights.get(steps)
    if table is None:
        table = []
        for step in range(steps):
            t = step / steps
            t2 = t * t
            t3 = t2 * t
            table.append((0.5 * (-t3 + 2.0 * t2 - t),
                          0.5 * (3.0 * t3 - 5.0 * t2 + 2.0),
                          0.5 * (-3.0 * t3 + 4.0 * t2 + t),
                          0.5 * (t3 - t2)))
        table = tuple(table)
        _weights[steps] = table
    return table


def curve(values, steps=CURVE_STEPS):
    """Resample `values` to an evenly spaced Catmull-Rom curve through them."""
    if steps < 2 or len(values) < 3:
        return values
    low, high = min(values), max(values)
    table = _basis(steps)
    last = len(values) - 1
    out = []
    for index in range(last):
        a = values[index - 1] if index else values[0]
        b = values[index]
        c = values[index + 1]
        d = values[index + 2] if index + 2 <= last else values[last]
        for w0, w1, w2, w3 in table:
            value = w0 * a + w1 * b + w2 * c + w3 * d
            out.append(low if value < low else (high if value > high else value))
    out.append(values[last])
    return out


def readable(pen, over, toward):
    """Return `pen` if it can be seen on `over`, else stepped toward `toward`."""
    for alpha in (255, 128):
        candidate = pen if alpha == 255 else pen.with_alpha(alpha).over(toward)
        if over.difference(candidate) >= SERIES_FLOOR:
            return candidate
    return toward


PIP_W, PIP_GAP, PIP_H = 14, 5, 4


def pips(theme, index, total):
    """Draw one pip per page, the current one in the accent."""
    k = look.FOOTER_H / 20.0
    w, gap = max(4, int(PIP_W * k)), max(2, int(PIP_GAP * k))
    h = max(2, int(PIP_H * k))
    span = total * w + (total - 1) * gap
    x = (look.W - span) // 2
    y = look.H - look.FOOTER_H + (look.FOOTER_H - h) // 2
    for i in range(total):
        screen.pen = theme.accent_b if i == index else theme.grid
        screen.shape(shape.rounded_rectangle(
            rect(x + i * (w + gap), y, w, h), min(h // 2, w // 2)))


def furniture(theme, title, index, total, subtitle=None):
    """Draw the header and footer bands."""
    rule = max(1, look.HEADER_H // 15)
    screen.pen = theme.panel
    screen.rectangle(rect(0, 0, look.W, look.HEADER_H))
    screen.rectangle(rect(0, look.H - look.FOOTER_H, look.W, look.FOOTER_H))
    screen.pen = theme.accent_b
    screen.rectangle(rect(0, look.HEADER_H - rule, look.W, rule))
    blit_label(title.upper(), look.SIZE_TITLE, theme.ink,
               look.PAD, (look.HEADER_H - look.SIZE_TITLE) // 2 - rule)
    if subtitle:
        blit_label(subtitle, look.SIZE_SMALL, theme.dim, look.W - look.PAD,
                   (look.HEADER_H - look.SIZE_SMALL) // 2 - rule, align=2)
    if total > 1:
        pips(theme, index, total)


LINE_W = 2.0
LINE_FLAGS = (shape.PATH_OPEN | shape.ALIGN_CENTER | shape.JOIN_MITER | shape.CAP_BUTT)


UNITS = {}
_readings = {}
GAUGE_FILL = "solid"
TRACK_ALPHA = 32
_gradients = {}

def column_width(texts, size, name=TEXT):
    """Return how wide a column of these strings has to be."""
    if not texts:
        return 0
    return text_width("\n".join(texts), size, name)

SEVERAL = 3

_points = array("f", b"")


def _rate(bps):
    """Format a throughput, scaled to the largest prefix it fills."""
    if bps >= 1024 * 1024 * 1024:
        return f"{bps / (1024.0 ** 3):.1f}G"
    if bps >= 1024 * 1024:
        return f"{bps / (1024.0 ** 2):.1f}M"
    if bps >= 1024:
        return f"{bps / 1024.0:.0f}K"
    return f"{bps:.0f}"

def _size(megabytes):
    """Format a size given in megabytes, scaled the same way a rate is."""
    if megabytes >= 1024 * 1024:
        return f"{megabytes / (1024.0 ** 2):.1f}T"
    if megabytes >= 1024:
        return f"{megabytes / 1024.0:.1f}G"
    return f"{megabytes:.0f}M"

def _duration(seconds):
    seconds = int(seconds)
    if seconds >= 86400:
        return f"{seconds // 86400}d{(seconds % 86400) // 3600}h"
    if seconds >= 3600:
        return f"{seconds // 3600}h{(seconds % 3600) // 60}m"
    return f"{seconds // 60}m"

def fmt(value, field):
    """Format a value short enough for its box."""
    if value is None:
        return "--"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return _several(value, field)
    if field.endswith("_bps"):
        return _rate(value)
    if field.endswith("_mb"):
        return _size(value)
    if field in ("uptime_s", "secs_left"):
        return _duration(value)
    if field in ("freq", "clock", "rpm", "procs"):
        return f"{value:.0f}"
    if isinstance(value, float):
        return f"{value:.0f}" if value >= 100 else f"{value:.1f}"
    return str(value)

def _several(values, field):
    if not values:
        return "--"
    if len(values) <= SEVERAL:
        return " ".join(fmt(item, field) for item in values)
    return f"{len(values)} values"

def use_units(units):
    """Take the units the layout carried."""
    global UNITS
    UNITS = units or {}
    _readings.clear()

def short_unit(field):
    """Return the unit that follows a formatted value."""
    if field.endswith("_bps"):
        return "B/s"
    if field == "cores" or field == "pct" or field.endswith("_pct"):
        return "%"
    if field == "temp":
        return "°C"
    if field in ("power", "package_w"):
        return "W"
    if field in ("freq", "clock"):
        return "MHz"
    if field.endswith("_mb"):
        return "B"
    if field in ("uptime_s", "secs_left"):
        return ""
    return UNITS.get(field, "")

def reading(value, field):
    """Format a value with its unit."""
    if type(value) is float or type(value) is int:
        key = (value, field)
        text = _readings.get(key)
        if text is not None:
            return text
        text = fmt(value, field) + short_unit(field)
        if len(_readings) > 240:
            _readings.clear()
        _readings[key] = text
        return text
    text = fmt(value, field)
    if value is None or isinstance(value, (str, bool, list, tuple)):
        return text
    return text + short_unit(field)

def swept_pens(theme, centre, radius, backwards=False):
    """Return the (fill, track) pens laying the theme's ramp round a gauge."""
    key = (theme.key, centre, radius, backwards)
    pens = _gradients.get(key)
    if pens is None:
        import math

        turn = (look.DIAL_TO - look.DIAL_FROM) / 360.0
        stops = [(pos * turn, pen) for pos, pen in theme.ramp]
        if backwards:
            stops = [(turn - pos, pen) for pos, pen in reversed(stops)]
        angle = math.radians(look.DIAL_FROM)
        towards = (centre[0] + math.sin(angle) * radius,
                   centre[1] - math.cos(angle) * radius)
        pens = _gradients[key] = tuple(
            brush.gradient(brush.CONICAL, centre[0], centre[1], towards[0], towards[1],
                           tuple((pos, pen if alpha == 255 else pen.with_alpha(alpha))
                                 for pos, pen in stops))
            for alpha in (255, TRACK_ALPHA))
    return pens

def blit_icon(character, size, pen, x, y, align=0, name=ICON_NAME):
    if not has_font(name):
        return 0
    return blit_label(character, size, pen, x, y, align=align, name=name)


def gauge(theme, centre, outer, inner, fraction, value_text, under=None,
          value_size=None, label_size=None, cold=False, icon=None, unit=None, hot=None,
          swept=None):
    """Draw one sweep gauge, with a line of text inside it."""
    value_size = value_size or look.SIZE_HUGE
    label_size = label_size or look.SIZE_LABEL
    middle = vec2(*centre)
    start, end = look.DIAL_FROM, look.DIAL_TO
    fraction = 0.0 if fraction is None else max(0.0, min(1.0, fraction))
    fill, track = swept if swept else (None, None)

    lit = not cold and fraction > 0.001
    sweep = start + (end - start) * fraction if lit else start
    screen.pen = theme.grid if track is None or cold else track
    if end - sweep > 0.5:
        screen.shape(shape.arc(middle, inner, outer, sweep, end))

    if lit:
        screen.pen = (theme.at(fraction if hot is None else hot) if fill is None else fill)
        screen.shape(shape.arc(middle, inner, outer, start, sweep))

        screen.pen = theme.ink
        screen.shape(shape.arc(middle, inner - look.px(3), outer + look.px(3),
                                sweep - 1.4, sweep + 1.4))

    ink = theme.dim if cold else theme.ink
    top = centre[1] - value_size * 0.62
    unit_size = max(look.SIZE_SMALL, int(value_size * 0.45))
    reading_w = text_width(value_text, value_size)
    suffix_w = text_width(unit, unit_size) if unit else 0
    if suffix_w and reading_w + suffix_w > inner * 2 - look.px(4):
        suffix_w = 0
    left = centre[0] - (reading_w + suffix_w) // 2
    blit_label(value_text, value_size, ink, left, top)
    if suffix_w:
        blit_label(unit, unit_size, theme.dim, left + reading_w,
                   top + value_size - unit_size)
    below = centre[1] + value_size * 0.42
    if icon and blit_icon(icon, label_size + look.px(8), theme.dim,
                          centre[0], below, align=1):
        return
    if under:
        blit_label(under, label_size, theme.dim, centre[0], below, align=1)

def dial(theme, fraction, value_text, unit_text, cold=False, hot=None, backwards=False):
    """Draw the single gauge of a `dial` page, with its readouts beside it."""
    gauge(theme, look.DIAL_C, look.DIAL_OUTER, look.DIAL_INNER, fraction, value_text,
          unit_text, cold=cold, hot=hot,
          swept=swept_pens(theme, look.DIAL_C, look.DIAL_OUTER, backwards)
          if GAUGE_FILL == "ramp" else None)

def dials(theme, entries):
    """Draw up to four gauges across the body band, each named under its reading."""
    shape_of = look.DIALS.get(len(entries)) or look.DIALS[4]
    for centre, entry in zip(shape_of["centres"], entries):
        name, value_text, fraction, icon, unit, hot = entry
        gauge(theme, centre, shape_of["outer"], shape_of["inner"], fraction, value_text,
              name, shape_of["value"], shape_of["label"], fraction is None, icon, unit,
              hot)

def readout(theme, y, name, value_text, fraction=None, note=None, chip=None, hot=None):
    """Draw one row of the column beside a gauge."""
    x = look.READOUT_X
    blit_label(name, look.SIZE_SMALL, theme.dim, x, y)
    blit_label(value_text, look.SIZE_VALUE, theme.ink, x, y + look.px(10))
    if chip:
        screen.pen = chip
        chip_w = look.px(10)
        screen.rectangle(rect(x + look.READOUT_W - chip_w, y + look.px(3),
                              chip_w, chip_w))
    if note:
        blit_label(note, look.SIZE_SMALL, theme.dim, x, y + look.px(29))
    elif fraction is not None:
        width = look.READOUT_W
        fraction = max(0.0, min(1.0, fraction))
        filled = int(width * fraction)
        screen.pen = theme.grid
        bar_h = max(1, look.px(3))
        screen.rectangle(rect(x + filled, y + look.px(28),
                              width - filled, bar_h))
        if filled:
            screen.pen = theme.at(fraction if hot is None else hot)
            screen.rectangle(rect(x, y + look.px(28), filled, bar_h))


COLUMN_GAP = 8
SMOOTH = True
SMOOTH_MIN_H = 40
WALK_LEAD = 2
WALK_MIN = 8
AXIS_STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500)
SERIES_ALPHA = (200, 150)

def flat(values):
    """Return `values` with its gaps moved to the axis."""
    if None not in values:
        return values
    return [0.0 if value is None else value for value in values]

def at_axis(value):
    """Return a single reading, with a missing one at the axis."""
    return 0.0 if value is None else value

def bars(theme, values, maximum=100.0, field="pct", fractions=None, names=None):
    """Draw a stack of horizontal bars."""
    if not values:
        return
    values = flat(values)
    count = min(len(values), 16)
    top = look.BODY_TOP + look.px(6)
    slot = max(look.px(6), (look.BODY_H - look.px(12)) // count)
    height = max(look.px(4), slot - look.px(3))
    names = ([str(names[i]) if i < len(names) else "" for i in range(count)] if names
             else [f"{i}" for i in range(count)])
    readings = [reading(values[i], field) for i in range(count)]
    label_w = column_width(names, look.SIZE_SMALL)
    value_w = column_width(readings, look.SIZE_SMALL)
    x = look.PAD + label_w + COLUMN_GAP
    width = max(look.px(20),
                look.W - x - look.px(COLUMN_GAP) - value_w - look.PAD)

    for i in range(count):
        value = values[i]
        if fractions is None:
            fraction = max(0.0, min(1.0, value / maximum if maximum else 0.0))
        else:
            fraction = fractions[i]
        y = top + i * slot
        blit_label(names[i], look.SIZE_SMALL, theme.dim, look.PAD,
                       y - look.px(1))
        filled = max(1, int(width * fraction)) if fraction > 0 else 0
        screen.pen = theme.grid
        screen.rectangle(rect(x + filled, y, width - filled, height))
        if filled:
            screen.pen = theme.at(fraction)
            screen.rectangle(rect(x, y, filled, height))
        blit_label(readings[i], look.SIZE_SMALL, theme.ink,
                   look.W - look.PAD, y - look.px(1), align=2)

def curve_steps(width, height, count):
    """Return how finely to subdivide `count` samples across a plot this size, 1 for not at all."""
    if not SMOOTH or count < 3 or height < look.px(SMOOTH_MIN_H):
        return 1
    return max(2, min(CURVE_STEPS, int(width / (count - 1))))

def _lay_out(left, top, width, height, values, peak, shift):
    """Lay `values` scaled against `peak` into the shared float buffer, returning the float count."""
    global _points
    values = flat(values)
    samples = len(values)
    if samples < 2:
        return 0
    count = samples
    steps = curve_steps(width, height, count)
    if steps > 1:
        count = (samples - 1) * steps + 1
    if len(_points) < (count + 2) * 2:
        _points = array("f", bytes((count + 2) * 8))
    per_sample = steps if steps > 1 else 1
    lead = per_sample * (WALK_LEAD if WALK_LEAD > 1 else 1)
    if lead > count // 4:
        lead = count // 4
    walking = shift is not None and samples >= WALK_MIN
    span = count - 1 - lead if walking and count > lead + 1 else count - 1
    step = width / float(span)
    scale = height / float(peak or 1.0)
    bottom = top + height
    away = shift * step * per_sample if walking else 0.0
    start = left - away
    i = 0
    if steps > 1:
        low, high = min(values), max(values)
        table = _basis(steps)
        last = samples - 1
        point = 0
        for index in range(last):
            a = values[index - 1] if index else values[0]
            b = values[index]
            c = values[index + 1]
            d = values[index + 2] if index + 2 <= last else values[last]
            for w0, w1, w2, w3 in table:
                value = w0 * a + w1 * b + w2 * c + w3 * d
                value = low if value < low else (high if value > high else value)
                y = bottom - value * scale
                _points[i] = start + point * step
                _points[i + 1] = top if y < top else (bottom if y > bottom else y)
                i += 2
                point += 1
        y = bottom - values[last] * scale
        _points[i] = start + point * step
        _points[i + 1] = top if y < top else (bottom if y > bottom else y)
        return i + 2
    for index in range(count):
        y = bottom - values[index] * scale
        _points[i] = start + index * step
        _points[i + 1] = top if y < top else (bottom if y > bottom else y)
        i += 2
    return i

def area(left, top, width, height, values, peak, base=None, shift=None):
    """Return a filled area shape from `values` against `peak`, closed along its base, or None."""
    i = _lay_out(left, top, width, height, values, peak, shift)
    if not i:
        return None
    if base is None:
        base = top + height
    _points[i] = _points[i - 2]
    _points[i + 1] = base
    _points[i + 2] = _points[0]
    _points[i + 3] = base
    return shape.custom(memoryview(_points)[:i + 4])

def line(left, top, width, height, values, peak, weight=LINE_W, shift=None):
    """Return `values` as a stroked polyline shape against `peak`, or None."""
    i = _lay_out(left, top, width, height, values, peak, shift)
    if not i:
        return None
    trace = shape.custom(memoryview(_points)[:i])
    trace.stroke(weight, LINE_FLAGS)
    return trace

def axis_top(peak, field):
    """Return the round number an axis tops out at, at or above `peak`."""
    base = 1024.0 if field.endswith(("_bps", "_mb")) else 10.0
    scale = 1.0
    while scale * AXIS_STEPS[-1] < peak:
        scale *= base
    for step in AXIS_STEPS:
        if scale * step >= peak:
            return scale * step
    return scale * base

def graph(theme, series, labels, maximum=None, shift=None):
    """Draw one or two series over time, as filled areas."""
    field = labels[0][1] if labels else "pct"
    if maximum is None:
        peak = axis_top(max((p for s in series for p in s if p is not None),
                            default=1.0), field)
    else:
        peak = max(maximum, 1.0) * 1.15

    peak_text = reading(peak, field)
    left = look.PAD + column_width((peak_text, "0"), look.SIZE_SMALL) + look.px(4)
    top = look.BODY_TOP + look.px(8)
    width = look.W - left - look.PAD
    height = look.BODY_H - look.px(26)

    screen.pen = theme.grid
    for i in range(5):
        y = top + int(height * i / 4.0)
        screen.hspan(left, y, width)

    if shift is not None and shift > WALK_LEAD and series and len(series[0]) >= WALK_MIN:
        stale = min(width, int((shift - WALK_LEAD) * width / float(len(series[0]) or 1)))
        if stale > 1:
            screen.pen = theme.grid
            for y in range(top, top + height, 4):
                screen.hspan(left + width - stale, y, stale)

    for index, points in enumerate(series):
        if not points or len(points) < 2:
            continue
        filled = area(left, top, width, height, points, peak, shift=shift)
        if filled is None:
            continue
        screen.alpha = _series_alpha(theme, index)
        screen.pen = _series_colour(theme, index)
        was = screen.clip
        screen.clip = rect(left, look.BODY_TOP, width, look.BODY_H)
        screen.shape(filled)
        screen.clip = was
    screen.alpha = 255

    blit_label(peak_text, look.SIZE_SMALL, theme.dim, look.PAD,
               top - look.px(4))
    blit_label("0", look.SIZE_SMALL, theme.dim, look.PAD,
               top + height - look.px(8))
    for index, (name, _field) in enumerate(labels[:2]):
        pen = _series_colour(theme, index)
        x = left + index * look.px(110)
        y = look.H - look.FOOTER_H - look.px(14)
        screen.pen = pen
        screen.rectangle(rect(x, y + look.px(3), look.px(10), look.px(4)))
        blit_label(name, look.SIZE_SMALL, theme.dim, x + look.px(14),
                   y - look.px(2))

def _series_alpha(theme, index):
    return SERIES_ALPHA[0] if index == 0 or theme.pale else SERIES_ALPHA[1]

def _series_colour(theme, index):
    """Return the colour for graph series `index`."""
    if index == 0:
        return theme.accent
    alpha = _series_alpha(theme, index)
    if theme.accent_b != theme.accent:
        if theme.bg.difference(theme.accent_b.with_alpha(alpha).over(theme.bg)) >= SERIES_FLOOR:
            return theme.accent_b
    cold, hot = theme.at(0.0), theme.at(1.0)
    order = ((cold, hot) if theme.accent.difference(cold) >= theme.accent.difference(hot)
             else (hot, cold))
    for pen in order:
        if theme.bg.difference(pen.with_alpha(alpha).over(theme.bg)) >= SERIES_FLOOR:
            return pen
    return theme.dim

def grid(theme, entries):
    """Draw up to six labelled figures in two rows, one panel each."""
    if not entries:
        return
    count = min(len(entries), 6)
    columns = 3 if count > 4 else max(1, min(count, 2)) if count <= 2 else 2
    if count in (3, 4):
        columns = 2
    if count > 4:
        columns = 3
    rows = (count + columns - 1) // columns
    cell_w = ((look.W - look.PAD * 2 - (columns - 1) * look.px(6))
              // columns)
    cell_h = ((look.BODY_H - look.px(12) - (rows - 1) * look.px(6)) // rows)

    for i in range(count):
        name, value_text, fraction, icon, hot = entries[i]
        column = i % columns
        row = i // columns
        x = look.PAD + column * (cell_w + look.px(6))
        y = look.BODY_TOP + look.px(6) + row * (cell_h + look.px(6))
        screen.pen = theme.panel
        screen.shape(shape.rounded_rectangle(rect(x, y, cell_w, cell_h),
                                             look.px(5)))
        if fraction is not None:
            screen.pen = theme.at(max(0.0, min(1.0, fraction if hot is None else hot)))
            bar = max(1, look.px(3))
            screen.rectangle(rect(x, y + cell_h - bar,
                                  int(cell_w * max(0.0, min(1.0, fraction))),
                                  bar))
        blit_label(name, look.SIZE_SMALL, theme.dim, x + look.px(7),
                   y + look.px(5))
        if icon:
            blit_icon(icon, look.SIZE_VALUE, theme.dim, x + cell_w - look.px(7),
                      y + look.px(4), align=2, name=SYMBOLS)
        size = look.SIZE_BIG if rows < 3 else look.SIZE_VALUE
        blit_label(value_text, size, theme.ink, x + 7, y + cell_h // 2 - size // 2 + 2)


def ago(seconds):
    """Format an age as "3m ago", or None where there is none."""
    if seconds is None:
        return None
    seconds = int(seconds)
    if seconds < 60:
        return "just now"
    if seconds < 5400:
        return "%dm ago" % (seconds // 60)
    if seconds < 172800:
        return "%dh ago" % (seconds // 3600)
    return "%dd ago" % (seconds // 86400)


def fit(text, size, room, name=TEXT):
    """Shorten a string until it fits `room` pixels, with an ellipsis if cut."""
    if text_width(text, size, name) <= room:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        if text_width(text[:middle] + "...", size, name) <= room:
            low = middle
        else:
            high = middle - 1
    return (text[:low] + "...") if low else text
