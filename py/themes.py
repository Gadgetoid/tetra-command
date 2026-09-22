"""Themes, loaded from themes.json."""

import json

import derive

DEFAULT = "dark"

PALE_FROM = 0.5

_data = None


def _load():
    global _data
    if _data is None:
        with open("themes.json") as handle:
            _data = json.load(handle)
    return _data


def THEMES():
    return _load()["themes"]


def ALIASES():
    return _load()["aliases"]


def _titled(text):
    return " ".join(word[:1].upper() + word[1:]
                    for word in text.split(" ") if word)


def label(name):
    record = THEMES().get(name) or {}
    given = record.get("label")
    return given or _titled(name.replace("-", " ").replace("_", " "))


def mode(name):
    themes = THEMES()
    record = themes.get(name) or themes[DEFAULT]
    spec = record.get("derived")
    lightness = (derive.SHAPES[spec["shape"]]["bg"] if spec
                 else derive.oklch(record["palette"]["bg"])[0])
    return "light" if lightness >= PALE_FROM else "dark"


def ORDER():
    return _load()["order"]


def records():
    themes = THEMES()
    return [{"name": name, "label": label(name), "mode": mode(name),
             "pair": themes[name].get("pair"),
             "derived": "derived" in themes[name]}
            for name in ORDER() if name in themes]


def resolve(name, tint):
    aliased = ALIASES().get(name)
    if not aliased:
        return name, tint
    at = (derive.ACCENT_HUES.index(int(aliased["hue"]))
          if "hue" in aliased else None)
    return aliased["theme"], (list(derive.accents("saturated")[at])
                              if at is not None else tint)


def palette(name, accent, second="same"):
    themes = THEMES()
    record = themes.get(name) or themes[DEFAULT]
    spec = record.get("derived")
    if spec:
        return derive.palette(tuple(accent), spec["shape"],
                              spec.get("bold", False), second)
    stored = record["palette"]
    out = {"ramp": tuple((at, tuple(rgb)) for at, rgb in stored["ramp"])}
    for role, value in stored.items():
        if role != "ramp":
            out[role] = tuple(value)
    out["image"] = derive.image_ramps(out["accent"])
    return out
