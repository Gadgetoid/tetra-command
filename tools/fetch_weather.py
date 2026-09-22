#!/usr/bin/env python3
"""Fetch one location's weather into the data directory as weather.json.

The badge never talks to the network: statsbadge's host app collects and pushes,
and the same split applies here. The app spawns this with --auto --watch and
reaps it on exit; it re-reads the file either way.

    fetch_weather.py "Cambridge"     one fetch, named place
    fetch_weather.py --auto --watch  follow location.json, keep it fresh

--auto takes the fix the app writes to location.json. Location Services will
only answer the app: it is the one with a bundle and a usage string, so the
coordinate has to come through a file rather than be asked for here.

The payload shape and the icon letters match statsbadge-clock, so clockface.py
reads it unmodified.
"""

import json
import os
import sys
import time
import urllib.parse
import urllib.request

from paths import take_data

INTERVAL_S = 900.0
# Nothing to do until the app has been granted Location Services and written a
# fix, which lands a second or two after we start, so look often rather than
# leaving the clock page blank for a whole interval.
WAIT_S = 3.0
# A quarter of an hour is a long time to keep running after the app has gone, so
# the wait is in slices and each one looks.
POLL_S = 2.0

# Open-Meteo weather_code -> condition, from statsbadge_clock/__init__.py
CONDITIONS = {
    0: "clear", 1: "fair", 2: "cloudy", 3: "overcast",
    45: "fog", 48: "fog",
    51: "drizzle", 53: "drizzle", 55: "drizzle",
    56: "sleet", 57: "sleet",
    61: "rain", 63: "rain", 65: "heavy rain",
    66: "sleet", 67: "sleet",
    71: "snow", 73: "snow", 75: "heavy snow", 77: "snow",
    80: "showers", 81: "showers", 82: "downpour",
    85: "snow", 86: "snow",
    95: "thunder", 96: "thunder", 99: "thunder",
}
# icons.af remaps Material Symbols onto ASCII letters (see icons.txt). Loading
# the real Material Symbols TTF instead, so emit the actual codepoints: the
# letters would draw as letters.
ICONS = {
    "clear": "\uf157",       # clear_day
    "fair": "\uf172",        # partly_cloudy_day
    "cloudy": "\uf15c",      # cloud
    "overcast": "\ue3dd",    # filter_drama
    "fog": "\ue818",         # foggy
    "drizzle": "\uf61e",     # rainy_light
    "rain": "\uf176",        # rainy
    "heavy rain": "\uf61f",  # rainy_heavy
    "downpour": "\uf61f",
    "sleet": "\uf61d",       # rainy_snow
    "showers": "\uf60b",     # weather_mix
    "snow": "\ue2cd",        # weather_snowy
    "heavy snow": "\uf61c",  # snowing_heavy
    "thunder": "\uebdb",     # thunderstorm
}
NIGHT_ICONS = {"clear": "\uf159", "fair": "\uf174"}  # clear_night, partly_cloudy_night


def geocode(place):
    url = ("https://geocoding-api.open-meteo.com/v1/search"
           f"?name={urllib.parse.quote(place)}&count=1")
    with urllib.request.urlopen(url, timeout=8) as r:
        results = json.loads(r.read().decode()).get("results") or []
    if not results:
        raise SystemExit(f"no such place: {place}")
    hit = results[0]
    return hit["latitude"], hit["longitude"], hit["name"]


def today(series):
    if isinstance(series, list) and series and isinstance(series[0], (int, float)):
        return series[0]
    return None


def fetch(lat, lon, label):
    url = ("https://api.open-meteo.com/v1/forecast"
           f"?latitude={lat}&longitude={lon}"
           "&current=temperature_2m,relative_humidity_2m,"
           "apparent_temperature,weather_code,wind_speed_10m,is_day"
           "&temperature_unit=celsius&wind_speed_unit=kmh"
           "&daily=temperature_2m_max,temperature_2m_min"
           "&timezone=auto")
    with urllib.request.urlopen(url, timeout=8) as r:
        payload = json.loads(r.read().decode())

    current = payload.get("current", {})
    code = current.get("weather_code")
    condition = CONDITIONS.get(code, "?") if code is not None else None
    night = current.get("is_day") == 0
    icon = NIGHT_ICONS.get(condition) if night else None
    daily = payload.get("daily") or {}
    return {
        "high": today(daily.get("temperature_2m_max")),
        "low": today(daily.get("temperature_2m_min")),
        "temp": current.get("temperature_2m"),
        "feels": current.get("apparent_temperature"),
        "humidity": current.get("relative_humidity_2m"),
        "wind": current.get("wind_speed_10m"),
        "condition": condition,
        "code": code,
        "place": label,
        "temp_unit": "C",
        "wind_unit": "km/h",
        "icon": icon or ICONS.get(condition),
        "utc_offset": payload.get("utc_offset_seconds"),
        # When this was read, not when the file was written: a page that cannot
        # tell a fresh reading from a three day old one draws both alike.
        "at": int(time.time()),
    }


def rest(seconds, orphan_exits):
    """Sleep, returning False if the app went away while we did.

    Wall clock on purpose: time.monotonic() is mach_absolute_time() on macOS,
    which stops while the machine sleeps.
    """
    until = time.time() + seconds
    while True:
        left = until - time.time()
        if left <= 0.0:
            return True
        time.sleep(min(POLL_S, left))
        if orphan_exits and os.getppid() == 1:
            return False


def located(out_dir):
    """Return (lat, lon, name) from the app's fix, or None if there is not one."""
    try:
        with open(out_dir / "location.json") as handle:
            fix = json.load(handle)
        lat, lon = float(fix["lat"]), float(fix["lon"])
    except Exception:
        return None
    # No name means the reverse geocode failed, which the coordinate itself
    # stands in for. It is the one label that is never wrong.
    return lat, lon, fix.get("place") or f"{lat:.2f}, {lon:.2f}"


def once(out_dir, where):
    lat, lon, name = where
    data = fetch(lat, lon, name)
    out = out_dir / "weather.json"
    out.write_text(json.dumps(data))
    return data, out


def main(argv):
    out_dir, args = take_data(argv)
    auto = "--auto" in args
    watch = "--watch" in args
    orphan_exits = "--exit-with-parent" in args
    named = [arg for arg in args if not arg.startswith("--")]

    while True:
        if auto:
            where = located(out_dir)
        else:
            place = named[0] if named else "Cambridge, GB"
            where = geocode(place.split(",")[0].strip())

        if where is None:
            if not watch:
                print("no location.json yet: is the app running, and allowed "
                      "Location Services?")
                return 1
            if not rest(WAIT_S, orphan_exits):
                return 0
            continue

        try:
            data, out = once(out_dir, where)
        except Exception as error:
            if not watch:
                raise
            print(f"weather: {error}")
        else:
            print(f"{data['place']} {where[0]:.4f},{where[1]:.4f} -> {out.name}")
            print(f"  {data['temp']}°{data['temp_unit']} {data['condition']} "
                  f"icon={data['icon']!r} H{data['high']} L{data['low']} "
                  f"wind {data['wind']} {data['wind_unit']}")
        if not watch:
            return 0
        if not rest(INTERVAL_S, orphan_exits):
            return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(0)
