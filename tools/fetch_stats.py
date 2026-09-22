#!/usr/bin/env python3
"""Sample this machine into the data directory as stats.json, for the stat pages.

Self-contained: psutil and the standard library, nothing else. What the pages
need is a frame (a reading per field), the rate peaks a gauge scales itself
against, and a history ring per plotted field.

Forked from statsbadge's host-side collector and its psutil source, cut down to
what these pages actually draw. See STATSBADGE-CLEANUP.md.

    uv run tools/fetch_stats.py --watch

The app spawns exactly this as a child and reaps it on exit. It re-reads the
file either way, so this can also be started and stopped underneath it.
"""

import json
import os
import platform
import re
import socket
import sys
import time
import urllib.parse
import urllib.request

import psutil

from paths import take_data

MB = 1024 * 1024
INTERVAL = 1.0

# One point per sample per plotted field. 64 is what a graph page draws.
POINTS = 64
HISTORY_LEN = 120

# A rate has no natural full scale: 100Mbit reads as pegged on a gigabit link
# and idle on a slow one, so a gauge is scaled by the busiest this machine has
# been. The peak decays so an overnight transfer does not flatten it for days,
# and the floor stops an idle link making a gauge twitch at every packet.
PEAK_HALF_LIFE_S = 600.0
PEAK_FLOOR = 64 * 1024.0
RATES = ("disk.read_bps", "disk.write_bps", "net.down_bps", "net.up_bps")

PLOTTED = ("cpu.pct", "mem.pct", "disk.read_bps", "disk.write_bps",
           "net.down_bps", "net.up_bps")

QUAKE_FEED = "https://earthquake.usgs.gov/fdsnws/event/1/query"
QUAKE_EVERY_S = 600.0
QUAKE_RETRY_S = 60.0
QUAKE_COUNT = 10
QUAKE_MIN_MAG = 4.0
PLACE_MAX = 64

# Interfaces that are never the one you mean.
SKIP_IFACE = ("lo", "utun", "gif", "stf", "awdl", "llw", "bridge", "veth",
              "docker")

# The chip's name with the trademarks, the word CPU and the clock speed taken
# out: "Intel(R) Core(TM) i7-10750H CPU @ 2.60GHz" is mostly punctuation.
_CPU_NOISE = re.compile(r"\((?:R|TM|r|tm)\)|\bCPU\b|\bProcessor\b"
                        r"|\s+\d+-Core\b|@.*$")


def rate(now, before, dt):
    """Bytes per second, clamped at zero so a counter reset reads as idle."""
    delta = now - before
    return 0 if delta < 0 else round(delta / dt)


def tidy_cpu(name):
    return " ".join(_CPU_NOISE.sub(" ", name).split()) or name


def cpu_name():
    system = platform.system()
    try:
        if system == "Darwin":
            import subprocess
            out = subprocess.run(["sysctl", "-n", "machdep.cpu.brand_string"],
                                 capture_output=True, text=True, timeout=2)
            if out.returncode == 0 and out.stdout.strip():
                return tidy_cpu(out.stdout.strip())
        elif system == "Linux":
            with open("/proc/cpuinfo") as handle:
                for line in handle:
                    if line.startswith("model name"):
                        return tidy_cpu(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return tidy_cpu(platform.processor() or platform.machine())


def default_disk():
    """The filesystem "how full is my disk" means.

    On macOS that is not "/": the root is a sealed read-only system volume
    sharing an APFS container with the data volume, so it reports the system's
    12G against the container's size, 9% on a disk that is 86% full. Both
    report the container's free space, so the data volume is the answer.
    """
    best = None
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except Exception:
            continue
        if best is None or usage.used > best[0]:
            best = (usage.used, part.mountpoint)
    return best[1] if best else "/"


def busiest_iface():
    """The interface carrying the most traffic that is up and not loopback.

    Guessing beats making anyone name their interface, and on a laptop moving
    between wifi and ethernet the guess is the one they want.
    """
    stats = psutil.net_if_stats()
    best = None
    for name, counters in psutil.net_io_counters(pernic=True).items():
        info = stats.get(name)
        if not info or not info.isup or name.startswith(SKIP_IFACE):
            continue
        total = counters.bytes_sent + counters.bytes_recv
        if best is None or total > best[0]:
            best = (total, name, counters)
    return (best[2], best[1]) if best else (None, None)


def quakes():
    """Recent notable events from USGS, in the shape the map draws."""
    query = urllib.parse.urlencode({"format": "geojson", "limit": QUAKE_COUNT,
                                    "orderby": "time",
                                    "minmagnitude": QUAKE_MIN_MAG})
    with urllib.request.urlopen(f"{QUAKE_FEED}?{query}", timeout=8) as reply:
        payload = json.loads(reply.read().decode("utf-8"))

    out = []
    for feature in payload.get("features") or ():
        properties = feature.get("properties") or {}
        where = (feature.get("geometry") or {}).get("coordinates") or ()
        # The feed returns a null magnitude while an event is under review.
        if properties.get("mag") is None or len(where) < 2:
            continue
        place = properties.get("place") or properties.get("title") or ""
        out.append({
            "mag": round(float(properties["mag"]), 1),
            "place": place.strip()[:PLACE_MAX],
            "lon": round(float(where[0]), 3),
            "lat": round(float(where[1]), 3),
            # Kilometres, negative for the few events placed above sea level.
            "depth": round(float(where[2]), 1) if len(where) > 2 else None,
            # The feed reports milliseconds.
            "at": int(properties.get("time", 0)) // 1000,
        })
    return out


class Sampler:
    def __init__(self):
        self.net_prev = None
        self.disk_prev = None
        self.peaks = {}
        self.history = {}
        self.quake_records = []
        self.quake_next = 0.0
        self.boot = psutil.boot_time()
        self.host = socket.gethostname().split(".")[0]
        self.chip = cpu_name()
        self.disk_path = default_disk()
        self.last_at = None
        # cpu_percent needs a prior call to have an interval to compare with.
        psutil.cpu_percent(interval=None)
        psutil.cpu_percent(interval=None, percpu=True)

    def sample(self):
        now = time.monotonic()
        dt = (now - self.last_at) if self.last_at else 0.0
        self.last_at = now

        cpu = {"pct": round(psutil.cpu_percent(interval=None), 1),
               "cores": [round(v, 1) for v
                         in psutil.cpu_percent(interval=None, percpu=True)]}
        try:
            freq = psutil.cpu_freq()
            if freq and freq.current:
                cpu["freq"] = round(freq.current)
        except Exception:
            pass
        try:
            cpu["load"] = [round(v, 2) for v in psutil.getloadavg()]
        except (OSError, AttributeError):
            pass
        try:
            cpu["procs"] = len(psutil.pids())
        except Exception:
            pass

        memory = psutil.virtual_memory()
        mem = {"pct": round(memory.percent, 1),
               "used_mb": round((memory.total - memory.available) / MB),
               "total_mb": round(memory.total / MB)}
        try:
            swap = psutil.swap_memory()
            mem["swap_pct"] = round(swap.percent, 1)
            mem["swap_used_mb"] = round(swap.used / MB)
        except Exception:
            pass

        disk = {}
        try:
            usage = psutil.disk_usage(self.disk_path)
            disk["pct"] = round(usage.percent, 1)
            disk["used_mb"] = round(usage.used / MB)
            disk["total_mb"] = round(usage.total / MB)
        except Exception:
            pass
        try:
            io = psutil.disk_io_counters()
            if io:
                if self.disk_prev and dt > 0:
                    disk["read_bps"] = rate(io.read_bytes,
                                            self.disk_prev.read_bytes, dt)
                    disk["write_bps"] = rate(io.write_bytes,
                                             self.disk_prev.write_bytes, dt)
                self.disk_prev = io
        except Exception:
            pass

        net = {}
        counters, iface = busiest_iface()
        if counters is not None:
            net["iface"] = iface
            net["up_total_mb"] = round(counters.bytes_sent / MB)
            net["down_total_mb"] = round(counters.bytes_recv / MB)
            prev = self.net_prev
            if prev and prev[0] == iface and dt > 0:
                net["up_bps"] = rate(counters.bytes_sent,
                                     prev[1].bytes_sent, dt)
                net["down_bps"] = rate(counters.bytes_recv,
                                       prev[1].bytes_recv, dt)
            self.net_prev = (iface, counters)

        power = {}
        try:
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        if battery is not None:
            power["battery_pct"] = round(battery.percent)
            power["charging"] = bool(battery.power_plugged)
            if battery.secsleft is not None and battery.secsleft >= 0:
                power["secs_left"] = int(battery.secsleft)

        frame = {
            "cpu": cpu, "mem": mem, "disk": disk, "net": net, "power": power,
            "sys": {"host": self.host, "cpu_name": self.chip,
                    "os": "%s %s" % (platform.system(), platform.release()),
                    "arch": platform.machine(),
                    "uptime_s": int(time.time() - self.boot)},
            "t": time.time(),
        }
        frame["quakes"] = self.take_quakes()
        self.push_peaks(frame, dt)
        self.push_history(frame)
        return frame

    def take_quakes(self):
        """The stored events, aged. Refetched on its own slow timer."""
        if time.monotonic() >= self.quake_next:
            try:
                self.quake_records = quakes()
                self.quake_next = time.monotonic() + QUAKE_EVERY_S
            except Exception as error:
                # Keep whatever was last fetched, and come back sooner.
                self.quake_next = time.monotonic() + QUAKE_RETRY_S
                print("quakes: %s" % error, file=sys.stderr)

        now = int(time.time())
        events = []
        for record in self.quake_records:
            event = dict(record)
            event["age_s"] = max(0, now - event.pop("at"))
            events.append(event)
        return {"events": events, "count": len(events),
                "biggest": max((e["mag"] for e in events), default=None),
                "latest": events[0]["mag"] if events else None}

    def push_peaks(self, frame, dt):
        decay = 0.5 ** (max(dt, 0.0) / PEAK_HALF_LIFE_S)
        for ref in RATES:
            group, field = ref.split(".", 1)
            value = (frame.get(group) or {}).get(field)
            if value is None:
                continue
            self.peaks[ref] = max(float(value),
                                  self.peaks.get(ref, 0.0) * decay, PEAK_FLOOR)
        if self.peaks:
            frame["peaks"] = {ref: round(value, 3)
                              for ref, value in self.peaks.items()}

    def push_history(self, frame):
        """One point per sample per field, a None where there was no reading.

        A plot reads times off a ring's positions, so a field with nothing in
        it gets a None rather than being left out: skipping would draw an
        intermittent field's history compressed and mis-timed.
        """
        for ref in PLOTTED:
            group, field = ref.split(".", 1)
            value = (frame.get(group) or {}).get(field)
            ring = self.history.get(ref)
            if ring is None:
                if value is None:
                    continue
                ring = self.history[ref] = []
            ring.append(None if value is None else round(float(value), 1))
            if len(ring) > HISTORY_LEN:
                del ring[0:len(ring) - HISTORY_LEN]

    def rings(self):
        return {ref: ring[-POINTS:] for ref, ring in self.history.items()}


def write(out, frame, rings):
    payload = {"frame": frame, "history": rings}
    # Written beside and moved, so the app never reads half a file.
    spare = out.with_suffix(".part")
    spare.write_text(json.dumps(payload, separators=(",", ":")))
    spare.replace(out)


def main(argv):
    data, argv = take_data(argv)
    out = data / "stats.json"
    watch = "--watch" in argv
    # Spawned as a child of the app, which cannot promise to reap us if it
    # crashes. Being reparented to launchd is how we find out it is gone.
    orphan_exits = "--exit-with-parent" in argv

    sampler = Sampler()
    try:
        # Rates need a previous reading to difference against, so the first
        # sample only primes them.
        sampler.sample()
        while True:
            time.sleep(INTERVAL)
            if orphan_exits and os.getppid() == 1:
                return 0
            frame = sampler.sample()
            write(out, frame, sampler.rings())
            if not watch:
                print("%s: cpu %s%%, %d series, %d quakes -> %s"
                      % (out.name, frame["cpu"]["pct"], len(sampler.history),
                         frame["quakes"]["count"], out))
                return 0
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
