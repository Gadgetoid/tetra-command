"""The Tetra panel app: clock, stats and settings pages over a touch panel."""

import builtins
import json
import os
import sys

import picovector
import host

for _name in ("image", "color", "shape", "rect", "vec2", "mat3", "brush",
              "tween", "font", "palette", "spritesheet", "algorithm"):
    setattr(builtins, _name, getattr(picovector, _name))

W, H = host.size()
builtins.screen = picovector.image(W, H, host.framebuffer())
screen.antialias = image.X4

sys.path.append("/ext")

import look

look.resize(W, H)

import draw
import pages

draw.add_font(draw.TEXT, "fonts/Lexend[wght].ttf", variations={"wght": 400})

import clockface

ICON_CHARS = ("\uf157\uf159\uf172\uf174\uf15c\ue3dd\ue818"
              "\uf61e\uf176\uf61f\uf61d\uf60b\ue2cd\uf61c\uebdb")

draw.add_font(clockface.WEATHER_FONT, "fonts/MaterialSymbolsOutlined.ttf",
              chars=ICON_CHARS)

draw.ICON_CENTRE = 0.5

DIGIT_CHARS = "0123456789: "
draw.add_font(clockface.DIGITS_FONT, "fonts/Lexend[wght].ttf",
              chars=DIGIT_CHARS, variations={"wght": 500})
draw.add_font(clockface.LCD_FONT, "fonts/DSEG7Classic-Bold.ttf",
              chars=DIGIT_CHARS)

draw.set_cap(clockface.DIGITS_FONT, 0.700)
draw.set_cap(clockface.LCD_FONT, 1.0)

import issmap  # noqa: F401
import macropad
import macros
import nav
import ui
import config
import themes
import display_settings
import stats_pages
import theme_settings
import clock_settings
from macros_config import ICON_CHARS as PAD_ICON_CHARS

draw.add_font(macropad.ICON_FONT, "fonts/MaterialSymbolsOutlined.ttf",
              chars=PAD_ICON_CHARS + display_settings.ICON_CHARS
              + nav.ICON_CHARS + stats_pages.ICON_CHARS)

runner = macros.Runner()

import hid
if not hid.ready():
    print("macros: Accessibility is NOT granted to this terminal -- keys will")
    print("        not reach other apps. System Settings > Privacy & Security >")
    print("        Accessibility, then add the app running this.")
else:
    print("macros: Accessibility granted, HID output live")

_grid_room = ui.columns(theme_settings.COLS)[0] + ui.GAP()
ui.plan_captions((
    ([themes.label(record["name"]) for record in themes.records()],
     _grid_room),
    ([label for _name, label, _spec, _digital in clock_settings.faces()],
     _grid_room),
))

theme = theme_settings.build_theme()

CAROUSELS = {
    nav.CONTENT: [
        {"id": "clock", "title": "Clock", "face": "amsterdam", "themed": False,
         "render": pages.EXTRA["clockface"]},
        {"id": "iss", "title": "ISS", "follow": "whole world",
         "render": pages.EXTRA["issmap"]},
        {"id": "cpu", "title": "CPU", "render": pages.EXTRA["cpu"]},
        {"id": "load", "title": "Load", "render": pages.EXTRA["load"]},
        {"id": "net", "title": "Network", "render": pages.EXTRA["net"]},
        {"id": "disk", "title": "Disk", "render": pages.EXTRA["disk"]},
        {"id": "quakes", "title": "Quakes", "follow": "biggest",
         "render": pages.EXTRA["quakes"]},
    ],
    nav.MACROS: [
        {"id": "pad", "title": "Macros", "render": pages.EXTRA["macropad"]},
    ],
    nav.SETTINGS: [
        {"id": "display", "title": "Display", "render": pages.EXTRA["display"],
         "touch": display_settings},
        {"id": "theme", "title": "Theme", "render": pages.EXTRA["theme"],
         "touch": theme_settings},
        {"id": "clock_settings", "title": "Clock", "touch": clock_settings,
         "render": pages.EXTRA["clock_settings"]},
    ],
}

CLOCK_PAGE = CAROUSELS[nav.CONTENT][0]


def apply_clock_config():
    CLOCK_PAGE["face"] = config.get("face")
    CLOCK_PAGE["themed"] = bool(config.get("clock_themed"))


apply_clock_config()

mode = nav.CONTENT
page_at = {name: 0 for name in CAROUSELS}

WEATHER_PATH = "/data/weather.json"
ISS_PATH = "/data/iss.json"

# The file is the signal to re-read; a timer drew the last run's weather until
# it next came round.
FEED_POLL_MS = 1000
# mtime is whole seconds, so a same-second rewrite leaves no trace. Size catches
# most of those, the backstop the rest.
FEED_BACKSTOP_MS = 60_000

_weather = {}
_iss = {}
_feed_stamps = {}
_feeds_read_at = -FEED_POLL_MS
_feeds_forced_at = 0


def _read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _written(path, force):
    """Return whether `path` is worth re-reading."""
    try:
        status = os.stat(path)
        stamp = (status[8], status[6])
    except Exception:
        stamp = None
    if force or stamp is None or stamp != _feed_stamps.get(path, False):
        _feed_stamps[path] = stamp
        return True
    return False


def refresh_feeds(ticks):
    global _weather, _iss, _feeds_read_at, _feeds_forced_at
    if ticks - _feeds_read_at < FEED_POLL_MS:
        return _weather
    _feeds_read_at = ticks
    force = ticks - _feeds_forced_at >= FEED_BACKSTOP_MS
    if force:
        _feeds_forced_at = ticks
    if _written(WEATHER_PATH, force):
        _weather = _read_json(WEATHER_PATH)
    if _written(ISS_PATH, force):
        _iss = _read_json(ISS_PATH)
    return _weather

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def frame_now(seq, ticks):
    """Return the slice of the host frame this page reads."""
    year, month, mday, hour, minute, second, weekday, _ = host.localtime()
    clock = {
        "hour": hour, "minute": minute, "seconds": second,
        "time": "%02d:%02d" % (hour, minute),
        "date": "%s %d %s" % (DAYS[weekday], mday, MONTHS[month - 1]),
    }
    weather = refresh_feeds(ticks)

    places = {}
    if weather:
        here = dict(weather)
        here.update(clock)
        places["clock"] = here

    return {"seq": seq, "clock": clock, "weather": weather, "places": places,
            "iss": _iss, "ticks": ticks}


SWIPE_MIN_DX = W // 8
SWIPE_MAX_DY = H // 5

_touch_start = {}
_claimed = set()


def handle_touch(page):
    """Drain the input queue and return (pages moved, mode asked for or None)."""
    moved, wanted = 0, None
    touch = page.get("touch")
    while True:
        event = host.poll()
        if event is None:
            return moved, wanted
        kind, finger, x, y = event
        now = host.ticks_ms()
        if kind == host.DOWN:
            _touch_start[finger] = (x, y)
            if nav.hit(x, y):
                continue
            if page["id"] == "pad":
                macro, held = macropad.on_down(x, y, now, theme)
                if macro:
                    runner.start(macro, hold=True)
            elif touch and touch.on_down(x, y, theme):
                _claimed.add(finger)
        elif kind == host.MOVE:
            if finger in _claimed and touch:
                touch.on_move(x, y)
                continue
            start = _touch_start.get(finger)
            if start and abs(x - start[0]) >= SWIPE_MIN_DX and runner.busy:
                runner.release()
        elif kind == host.UP:
            start = _touch_start.pop(finger, None)
            runner.release()
            if finger in _claimed:
                _claimed.discard(finger)
                if touch:
                    touch.on_release()
                continue
            if start is None:
                continue
            icon = nav.hit(*start)
            if icon:
                wanted = nav.CONTENT if icon == mode else icon
                continue
            dx, dy = x - start[0], y - start[1]
            if abs(dx) >= SWIPE_MIN_DX and abs(dy) <= SWIPE_MAX_DY:
                moved = -1 if dx > 0 else 1
            elif page["id"] == "pad":
                macropad.on_release(now)
                runner.start(macropad.on_tap(start[0], start[1], now, theme))
            elif touch:
                touch.on_tap(start[0], start[1])


frames = 0
seq = 0
last_second = -1
t_start = host.ticks_ms()

while True:
    carousel = CAROUSELS[mode]
    page = carousel[page_at[mode]]
    step, wanted = handle_touch(page)
    if wanted and wanted != mode:
        mode = wanted
        _claimed.clear()
        macropad.close_modal()
        runner.cancel()
        carousel = CAROUSELS[mode]
        page = carousel[page_at[mode]]
    elif step:
        page_at[mode] = (page_at[mode] + step) % len(carousel)
        page = carousel[page_at[mode]]
        macropad.close_modal()
        runner.cancel()

    if theme_settings.take_change():
        theme = theme_settings.build_theme()
        draw.clear_cache()
    if clock_settings.take_change():
        apply_clock_config()

    runner.step()

    now = host.localtime()[5]
    if now != last_second:
        last_second = now
        seq += 1

    frame = frame_now(seq, host.ticks_ms())

    screen.pen = theme.bg
    screen.clear()
    page["render"](page, frame, None, theme)
    draw.furniture(theme, page["title"], page_at[mode], len(carousel))
    nav.render(theme, mode)

    frames += 1
    if frames % 300 == 0:
        elapsed = host.ticks_ms() - t_start
        print("frame", frames, "%.1f fps" % (frames * 1000.0 / elapsed))

    host.present()
