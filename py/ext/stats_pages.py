"""The stat pages, drawn from stats.json as tools/fetch_stats.py writes it."""

import json

import draw
import look
import pages
import quakemap

PATH = "/data/stats.json"
REFRESH_MS = 500

DISK_ICONS = {
    "pct": "\ue9e4",
    "read_bps": "\uf09b",
    "write_bps": "\uf090",
    "used_mb": "\ueff2",
}

ICON_CHARS = "".join(DISK_ICONS.values())

_data = {"frame": {}, "history": {}}
_read_at = -REFRESH_MS


def refresh(ticks):
    global _data, _read_at
    if ticks - _read_at < REFRESH_MS:
        return _data
    _read_at = ticks
    try:
        with open(PATH) as handle:
            _data = json.load(handle)
    except Exception:
        pass
    return _data


def value(frame, ref):
    """Return "group.field" out of the frame."""
    if not ref or "." not in ref:
        return None
    group, field = ref.split(".", 1)
    holder = frame.get(group)
    if not isinstance(holder, dict):
        return None
    return holder.get(field)


def peak(frame, ref):
    got = (frame.get("peaks") or {}).get(ref)
    return float(got) if got else None


def fraction(frame, ref, full=None):
    """Return where a reading sits on 0-1."""
    got = value(frame, ref)
    if got is None or isinstance(got, (str, bool, list, tuple)):
        return None
    top = full or (100.0 if ref.endswith(".pct") else peak(frame, ref))
    if not top:
        return None
    return max(0.0, min(1.0, float(got) / float(top)))


def _missing(theme):
    draw.blit_label("no stats: run tools/fetch_stats.py --watch",
                    look.SIZE_VALUE, theme.dim, look.W // 2,
                    draw.centre_y(look.SIZE_VALUE, look.BODY_MID), align=1)


def render_cpu(page, host_frame, _history, theme):
    frame = refresh(host_frame.get("ticks", 0)).get("frame") or {}
    cpu = frame.get("cpu") or {}
    if not cpu:
        _missing(theme)
        return

    pct = cpu.get("pct")
    draw.dial(theme, fraction(frame, "cpu.pct"), draw.fmt(pct, "pct"), "%")

    load = cpu.get("load")
    cores = cpu.get("cores") or []
    rows = [("LOAD", draw.fmt(load[0], "load") if load else "--",
             min(1.0, load[0] / max(1, len(cores))) if load else None, None)]

    freq = cpu.get("freq")
    if freq and freq > 100:
        rows.append(("CLOCK", draw.reading(freq, "freq"), None, None))
    else:
        rows.append(("CORES", str(len(cores)) if cores else "--", None, None))

    rows.append(("PROCS", draw.fmt(cpu.get("procs"), "procs"), None, None))
    rows.append(("MEMORY",
                 draw.fmt((frame.get("mem") or {}).get("pct"), "pct") + "%",
                 fraction(frame, "mem.pct"), None))
    for y, (name, text, part, note) in zip(look.readout_rows(len(rows)), rows):
        draw.readout(theme, y, name, text, part, note)


def series(data, ref):
    """Return one history ring, or an empty list where there is none."""
    got = (data.get("history") or {}).get(ref)
    return got if isinstance(got, list) else []


def render_net(page, host_frame, _history, theme):
    data = refresh(host_frame.get("ticks", 0))
    down, up = series(data, "net.down_bps"), series(data, "net.up_bps")
    if not down and not up:
        _missing(theme)
        return
    draw.graph(theme, (down, up),
               (("DOWN", "down_bps"), ("UP", "up_bps")))


def render_load(page, host_frame, _history, theme):
    data = refresh(host_frame.get("ticks", 0))
    cpu = series(data, "cpu.pct")
    if not cpu:
        _missing(theme)
        return
    draw.graph(theme, (cpu,), (("CPU", "pct"),), maximum=100.0)


def render_disk(page, host_frame, _history, theme):
    frame = refresh(host_frame.get("ticks", 0)).get("frame") or {}
    disk = frame.get("disk") or {}
    if not disk:
        _missing(theme)
        return
    used = disk.get("used_mb")
    entries = [
        ("FULL", draw.fmt(disk.get("pct"), "pct") + "%",
         fraction(frame, "disk.pct"), DISK_ICONS["pct"], None),
        ("READ", draw.reading(disk.get("read_bps"), "read_bps"),
         fraction(frame, "disk.read_bps"), DISK_ICONS["read_bps"], None),
        ("WRITE", draw.reading(disk.get("write_bps"), "write_bps"),
         fraction(frame, "disk.write_bps"), DISK_ICONS["write_bps"], None),
        ("USED", draw.reading(used, "used_mb") if used is not None else "--",
         None, DISK_ICONS["used_mb"], None),
    ]
    draw.grid(theme, entries)


def render_quakes(page, host_frame, _history, theme):
    """Hand the quakes extension the frame it draws itself from."""
    frame = refresh(host_frame.get("ticks", 0)).get("frame") or {}
    if not (frame.get("quakes") or {}).get("events"):
        _missing(theme)
        return
    quakemap.render(page, dict(frame, ticks=host_frame.get("ticks", 0)),
                    None, theme)


pages.EXTRA["cpu"] = render_cpu
pages.EXTRA["net"] = render_net
pages.EXTRA["load"] = render_load
pages.EXTRA["disk"] = render_disk
pages.EXTRA["quakes"] = render_quakes
for _kind in ("cpu", "net", "load", "disk", "quakes"):
    pages.ANIMATED.add(_kind)
