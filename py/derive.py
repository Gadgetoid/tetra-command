"""Build a whole palette out of one accent colour, in OKLCH."""

import math

ACCENT_HUES = tuple(range(0, 360, 30))
ACCENT_FAMILIES = {
    "pastel": (0.86, 0.34),
    "normal": (0.72, 0.62),
    "saturated": (0.68, 0.98),
    "dark": (0.45, 0.85),
}
DEFAULT_FAMILY = "normal"
ACCENT_RATIO = 1.8
HOT_C = 0.21
MONO_TRAVEL = 0.30
BOLD_TOWARD = 0.23
BOLD_AWAY = 0.20

SHAPES = {
    "dark": {"bg": 0.193, "panel": 0.237, "grid": 0.323, "dim": 0.665, "ink": 0.971,
             "hot": 0.560, "chroma": 0.020},
    "light": {"bg": 0.977, "panel": 0.944, "grid": 0.862, "dim": 0.486, "ink": 0.220,
              "hot": 0.400, "chroma": 0.012},
    "glow-dark": {"bg": 0.225, "panel": 0.272, "grid": 0.350, "dim": 0.600, "ink": 0.855,
                  "share": 0.58, "ink_ratio": 4.5, "dim_ratio": 2.2},
    "glow-light": {"bg": 0.930, "panel": 0.888, "grid": 0.820, "dim": 0.545, "ink": 0.345,
                   "share": 0.55, "ink_ratio": 4.5, "dim_ratio": 2.2},
}
DEFAULT_SHAPE = "dark"

ROLE_CHROMA = {"bg": 1.0, "panel": 1.0, "grid": 1.5, "ink": 0.7, "dim": 1.8}
ROLE_SHARE = {"bg": 1.0, "panel": 1.0, "grid": 1.0, "ink": 0.55, "dim": 1.0}

INK_RATIO = 7.0
DIM_RATIO = 4.5

SIGNAL_HUE = 30.0
SIGNAL_NEAR = 45.0

ACCENT_B_RULES = ("same", "complementary", "triadic", "contrasting")
ACCENT_B_TURNS = {"same": 0.0, "triadic": 120.0, "complementary": 180.0}


def to_linear(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def to_srgb(c):
    c = 12.92 * c if c <= 0.0031308 else 1.055 * (max(c, 0.0) ** (1 / 2.4)) - 0.055
    return max(0, min(255, round(c * 255)))


def oklch(rgb):
    """Return (lightness 0-1, chroma, hue in degrees) for an sRGB triple."""
    r, g, b = (to_linear(v) for v in rgb)
    long = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    medium = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    short = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    long, medium, short = long ** (1 / 3), medium ** (1 / 3), short ** (1 / 3)
    lightness = 0.2104542553 * long + 0.7936177850 * medium - 0.0040720468 * short
    green_red = 1.9779984951 * long - 2.4285922050 * medium + 0.4505937099 * short
    blue_yellow = 0.0259040371 * long + 0.7827717662 * medium - 0.8086757660 * short
    return (lightness,
            math.sqrt(green_red * green_red + blue_yellow * blue_yellow),
            math.degrees(math.atan2(blue_yellow, green_red)) % 360.0)


def _linear(lightness, chroma, hue):
    """Return linear-light RGB for an OKLCH colour, outside 0-1 when out of gamut."""
    radians = math.radians(hue)
    green_red = math.cos(radians) * chroma
    blue_yellow = math.sin(radians) * chroma
    long = lightness + 0.3963377774 * green_red + 0.2158037573 * blue_yellow
    medium = lightness - 0.1055613458 * green_red - 0.0638541728 * blue_yellow
    short = lightness - 0.0894841775 * green_red - 1.2914855480 * blue_yellow
    long, medium, short = long ** 3, medium ** 3, short ** 3
    return (4.0767416621 * long - 3.3077115913 * medium + 0.2309699292 * short,
            -1.2684380046 * long + 2.6097574011 * medium - 0.3413193965 * short,
            -0.0041960863 * long - 0.7034186147 * medium + 1.7076147010 * short)


def _in_gamut(linear):
    return all(-0.0015 <= channel <= 1.0015 for channel in linear)


def rgb(lightness, chroma, hue):
    """Return an sRGB triple for an OKLCH colour, reducing chroma to reach the gamut."""
    for attempt in range(12):
        linear = _linear(lightness, chroma, hue)
        if _in_gamut(linear) or not chroma:
            return tuple(to_srgb(channel) for channel in linear)
        chroma *= 0.92 if attempt else 0.98
    return tuple(to_srgb(channel) for channel in linear)


def max_chroma(lightness, hue):
    """Return the most chroma sRGB can hold at that lightness and hue."""
    low, high = 0.0, 0.4
    for _ in range(16):
        middle = (low + high) / 2.0
        if _in_gamut(_linear(lightness, middle, hue)):
            low = middle
        else:
            high = middle
    return low


def contrast(one, other):
    """Return the WCAG 2.1 ratio between two sRGB triples, 1.0 to 21.0."""
    def luminance(colour):
        r, g, b = (to_linear(v) for v in colour)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    first, second = luminance(one), luminance(other)
    if second > first:
        first, second = second, first
    return (first + 0.05) / (second + 0.05)


def readable_on(lightness, chroma, hue, background, ratio):
    """Return that colour, or the nearest one clearing `ratio` against `background`."""
    wanted = rgb(lightness, chroma, hue)
    if contrast(wanted, background) >= ratio:
        return wanted
    away = 1.0 if lightness >= oklch(background)[0] else -1.0
    for step in range(1, 101):
        moved = lightness + away * step * 0.01
        if not 0.0 <= moved <= 1.0:
            break
        candidate = rgb(moved, chroma, hue)
        if contrast(candidate, background) >= ratio:
            return candidate
    return rgb(1.0 if away > 0 else 0.0, 0.0, hue)


def accents(family=DEFAULT_FAMILY):
    """Return the twelve accents of one family, as sRGB triples."""
    lightness, part = ACCENT_FAMILIES.get(family, ACCENT_FAMILIES[DEFAULT_FAMILY])
    return [rgb(lightness, max_chroma(lightness, float(hue)) * part, float(hue))
            for hue in ACCENT_HUES]


def family_of(accent):
    """Return which family a stored accent came from, or the default."""
    wanted = tuple(accent)
    for family in ACCENT_FAMILIES:
        if wanted in [tuple(offer) for offer in accents(family)]:
            return family
    return DEFAULT_FAMILY


def offered():
    """Return every accent every family offers."""
    return [tuple(accent) for family in ACCENT_FAMILIES for accent in accents(family)]


def apart(one, other):
    """Return how far apart two sRGB colours are in OKLab, black to white being 100."""
    def lab(colour):
        lightness, chroma, hue = oklch(colour)
        radians = math.radians(hue)
        return (lightness, chroma * math.cos(radians), chroma * math.sin(radians))

    first, second = lab(one), lab(other)
    return 100.0 * math.sqrt(sum((a - b) ** 2 for a, b in zip(first, second)))


def second_accent(accent, rule="same"):
    """Return the accent used sparingly beside the first, by one of the rules."""
    lightness, chroma, hue = oklch(accent)
    if rule not in ACCENT_B_RULES or rule == "same":
        return tuple(accent)
    limit = max_chroma(lightness, hue)
    part = min(1.0, chroma / limit) if limit else 0.0
    if rule == "contrasting":
        offers = [rgb(lightness, max_chroma(lightness, float(turn)) * part, float(turn))
                  for turn in ACCENT_HUES]
        return max(offers, key=lambda offer: apart(accent, offer))
    turned = (hue + ACCENT_B_TURNS[rule]) % 360.0
    return rgb(lightness, max_chroma(lightness, turned) * part, turned)


def ramp_for(accent):
    """Return the ramp that suits this accent, `signal` or `mono`."""
    hue = oklch(accent)[2]
    away = abs((hue - SIGNAL_HUE + 180.0) % 360.0 - 180.0)
    return "signal" if away >= SIGNAL_NEAR else "mono"


def _signal_ramp(lightness, chroma, hue, shape):
    """Build a ramp cold at the accent's hue and hot at red, going the short way round."""
    turn = (SIGNAL_HUE - hue + 540.0) % 360.0 - 180.0
    hot = shape["hot"]
    stops = []
    for position, part in ((0.0, 0.0), (0.45, 0.42), (0.72, 0.74), (1.0, 1.0)):
        eased = part * part
        stops.append((position, rgb(lightness + (hot - lightness) * eased,
                                    chroma + (HOT_C - chroma) * eased,
                                    hue + turn * part)))
    return tuple(stops)


def _mono_ramp(lightness, chroma, hue, shape):
    """Build a ramp of one hue, saying severity with lightness and chroma."""
    away = MONO_TRAVEL if shape["bg"] < 0.5 else -MONO_TRAVEL
    hot = min(0.98, max(0.06, lightness + away))
    cold = min(0.98, max(0.06, hot - away))
    stops = []
    for position, part in ((0.0, 0.0), (0.5, 0.5), (1.0, 1.0)):
        stops.append((position, rgb(cold + (hot - cold) * part,
                                    chroma + (HOT_C - chroma) * part, hue)))
    return tuple(stops)


def _bold_ramp(lightness, chroma, hue, shape):
    """Build a ramp sweeping one hue from dark, through the accent, to pale."""
    toward = BOLD_TOWARD if shape["bg"] < 0.5 else -BOLD_TOWARD
    stops = []
    for position, level, part in ((0.0, lightness - toward, 0.9),
                                  (0.7, lightness, 1.0),
                                  (1.0, lightness + toward * (BOLD_AWAY / BOLD_TOWARD), 0.85)):
        stops.append((position, rgb(min(0.97, max(0.06, level)), chroma * part, hue)))
    return tuple(stops)


IMAGE_DARK = 0.16
IMAGE_LIGHT = 0.94
IMAGE_LEVELS = (4, 8)


def image_ramp(accent, levels):
    """Return the shades a picture of `levels` is drawn in, darkest first."""
    if levels < 2:
        levels = 2
    lightness, chroma, hue = oklch(accent)
    limit = max_chroma(lightness, hue)
    share = (chroma / limit) if limit else 0.0
    span = (IMAGE_LIGHT - IMAGE_DARK) / (levels - 1)
    shades = []
    for step in range(levels):
        level = IMAGE_DARK + span * step
        shades.append(rgb(level, max_chroma(level, hue) * share, hue))
    return tuple(shades)


def image_ramps(accent):
    """Return both level counts, keyed by how many, as a palette stores them."""
    return {str(levels): [list(colour) for colour in image_ramp(accent, levels)]
            for levels in IMAGE_LEVELS}


def tone(shape, role, hue):
    """Return the lightness and chroma a role takes in this shape, at this hue."""
    level = shape[role]
    if "share" in shape:
        return level, max_chroma(level, hue) * shape["share"] * ROLE_SHARE[role]
    return level, shape["chroma"] * ROLE_CHROMA[role]


def palette(accent, shape="dark", bold=False, second="same"):
    """Build a whole palette from one accent."""
    shape = SHAPES.get(shape, SHAPES[DEFAULT_SHAPE])
    lightness, chroma, hue = oklch(accent)
    background = rgb(*tone(shape, "bg", hue), hue)
    placed = readable_on(lightness, chroma, hue, background, ACCENT_RATIO)
    lightness, chroma, _hue = oklch(placed)
    build = _bold_ramp if bold else (_signal_ramp if ramp_for(accent) == "signal"
                                     else _mono_ramp)

    def at(role, ratio=None):
        level, own = tone(shape, role, hue)
        if ratio is None:
            return rgb(level, own, hue)
        return readable_on(level, own, hue, background, ratio)

    settled = rgb(lightness, chroma, hue)
    return {
        "bg": background,
        "panel": at("panel"),
        "ink": at("ink", shape.get("ink_ratio", INK_RATIO)),
        "dim": at("dim", shape.get("dim_ratio", DIM_RATIO)),
        "accent": settled,
        "accent_b": second_accent(settled, second),
        "grid": at("grid"),
        "ramp": build(lightness, chroma, hue, shape),
        "image": image_ramps(settled),
    }
