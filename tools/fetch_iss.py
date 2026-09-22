#!/usr/bin/env python3
"""Fetch the ISS position and ground track into the data directory as iss.json.

Same split as the weather: the badge side never talks to the network. The
payload shape matches statsbadge-iss, so issmap.py reads it unmodified.
"""

import json
import sys
import time
import urllib.request

from paths import take_data

WHERE = "https://api.wheretheiss.at/v1/satellites/25544"
CREW = "http://api.open-notify.org/astros.json"

TRACK_STEP_S = 300
TRACK_BACK, TRACK_AHEAD = 9, 10


def get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read().decode())


def where_now():
    p = get(WHERE)
    return {
        "lat": round(float(p["latitude"]), 3),
        "lon": round(float(p["longitude"]), 3),
        "altitude": round(float(p.get("altitude") or 0), 1),
        "speed": round(float(p.get("velocity") or 0), 1),
        "sunlit": p.get("visibility") != "eclipsed",
        "unit": "km",
        "solar_lat": round(float(p["solar_lat"]), 2),
        "solar_lon": round(float(p["solar_lon"]), 2),
        "at": int(p.get("timestamp") or time.time()),
        "age_s": 0,
    }


def track_now():
    """(lon, lat, sunlit) every TRACK_STEP_S, from TRACK_BACK behind to TRACK_AHEAD on."""
    now = int(time.time())
    wanted = [now + step * TRACK_STEP_S
              for step in range(-TRACK_BACK, TRACK_AHEAD + 1)]
    points = []
    for start in range(0, len(wanted), 10):
        stamps = ",".join(str(w) for w in wanted[start:start + 10])
        for entry in get(f"{WHERE}/positions?timestamps={stamps}") or ():
            points.append((round(float(entry["longitude"]), 2),
                           round(float(entry["latitude"]), 2),
                           0 if entry.get("visibility") == "eclipsed" else 1))
    return points, wanted[0]


def crew_count():
    try:
        people = get(CREW).get("people") or []
        return len([p for p in people if p.get("craft") == "ISS"])
    except Exception:
        return None


if __name__ == "__main__":
    where = where_now()
    track, track_from = track_now()
    data = {
        "where": where,
        "track": track,
        "track_from": track_from,
        "flown": round((time.time() - track_from) / TRACK_STEP_S, 2),
        "aboard": crew_count(),
    }
    out = take_data(sys.argv[1:])[0] / "iss.json"
    out.write_text(json.dumps(data))
    print(f"ISS at {where['lat']:.2f},{where['lon']:.2f} "
          f"alt {where['altitude']}km speed {where['speed']}km/h "
          f"{'sunlit' if where['sunlit'] else 'eclipsed'}")
    print(f"  track {len(track)} points, flown {data['flown']}, aboard {data['aboard']}")
