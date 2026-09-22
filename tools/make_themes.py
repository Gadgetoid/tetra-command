#!/usr/bin/env python3
"""Convert themes.toml into py/themes.json.

MicroPython has no tomllib, so the written palettes travel as JSON. The tinted
themes are not written down anywhere: they carry a `derived` spec and
py/derive.py builds them from whichever accent is picked.

themes.toml is vendored from statsbadge and is this project's copy now. It is
the source of truth for the palettes; re-run this when it changes.
"""

import json
import sys
import tomllib
from pathlib import Path

TOML = Path(__file__).resolve().parent.parent / "themes.toml"
OUT = Path(__file__).resolve().parent.parent / "py/themes.json"

ROLES = ("bg", "panel", "ink", "dim", "accent", "grid")

if __name__ == "__main__":
    if not TOML.exists():
        print(f"missing: {TOML}", file=sys.stderr)
        raise SystemExit(1)

    data = tomllib.loads(TOML.read_text(encoding="utf-8"))
    aliases = data.pop("aliases", {})

    themes = {}
    for name, record in data.items():
        entry = {"label": record.get("label"), "pair": record.get("pair")}
        derived = record.get("derived")
        if derived:
            entry["derived"] = {"shape": derived["shape"],
                                "bold": bool(derived.get("bold", False))}
        else:
            palette = {role: list(record[role]) for role in ROLES}
            if "accent_b" in record:
                palette["accent_b"] = list(record["accent_b"])
            palette["ramp"] = [[at, list(rgb)] for at, rgb in record["ramp"]]
            entry["palette"] = palette
        themes[name] = entry

    # MicroPython dicts do not keep insertion order, so the toml's order
    # travels as a list or every picker shows them shuffled.
    OUT.write_text(json.dumps({"themes": themes, "order": list(themes),
                               "aliases": aliases},
                              separators=(",", ":")))
    written = sum(1 for e in themes.values() if "palette" in e)
    print(f"{len(themes)} themes ({written} written, "
          f"{len(themes) - written} derived) -> {OUT.relative_to(OUT.parent.parent)}")
