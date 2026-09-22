"""A theme picker: named palettes on their own tabs, tinted ones with a colour grid."""

import math

import config
import derive
import draw
import look
import pages
import themes
import ui

DARK, LIGHT, TINTED = "dark", "light", "tinted"

TABS = ((DARK, "Dark"), (LIGHT, "Light"), (TINTED, "Tinted"))

COLS = 6

FAMILIES = ("pastel", "normal", "saturated", "dark")

N_IDLE, N_DOWN = 4.0, 7.0

SAMPLE = "63"

_layout = None
_built_for = None
_changed = False
_mode = None
_offered = {}


def _accents(family):
    got = _offered.get(family)
    if got is None:
        got = [tuple(one) for one in derive.accents(family)]
        _offered[family] = got
    return got


def _swatch_colours(name):
    record = themes.THEMES().get(name) or {}
    spec = record.get("derived")
    if spec:
        built = derive.palette(tuple(config.get("tint")), spec["shape"],
                               spec.get("bold", False), config.get("second"))
        return built["bg"], built["panel"], built["accent"]
    stored = record.get("palette") or {}
    return (tuple(stored.get("bg", (0, 0, 0))),
            tuple(stored.get("panel", (0, 0, 0))),
            tuple(stored.get("accent", (255, 255, 255))))


def build_theme():
    name = config.get("theme")
    palette = themes.palette(name, config.get("tint"), config.get("second"))
    return look.from_palette(name, palette) or look.get(look.DEFAULT)


def take_change():
    global _changed
    was, _changed = _changed, False
    return was


def _derived_now():
    record = themes.THEMES().get(config.get("theme")) or {}
    return "derived" in record


def _tint_at():
    wanted = tuple(config.get("tint"))
    for family in FAMILIES:
        offered = _accents(family)
        if wanted in offered:
            return family, offered.index(wanted)
    return None, None


def _in_tab(record, mode):
    """Return whether a theme record belongs on this tab."""
    if record["derived"]:
        return mode == TINTED
    return mode == record["mode"]


def _mode_now():
    global _mode
    if _mode is None:
        record = themes.THEMES().get(config.get("theme")) or {}
        _mode = (TINTED if "derived" in record
                 else themes.mode(config.get("theme")))
    return _mode


def _layout_unit_size(value_size):
    return max(8, int(value_size * 0.5))


def _swept(built, centre, radius):
    turn = (look.DIAL_TO - look.DIAL_FROM) / 360.0
    stops = tuple((pos * turn, pen) for pos, pen in built.ramp)
    angle = math.radians(look.DIAL_FROM)
    return brush.gradient(brush.CONICAL, centre[0], centre[1],
                          centre[0] + math.sin(angle) * radius,
                          centre[1] - math.cos(angle) * radius, stops)


def _cell(x, y, w, h, record, gap):
    name = record["name"]
    bg, panel, accent = _swatch_colours(name)
    built = look.from_palette(name, themes.palette(name, config.get("tint"),
                                                   config.get("second")))
    pad = look.px(4)
    outer = int(min(w // 4, h // 2) - look.px(2))
    inner = int(outer * 0.62)
    dial = (x + pad + outer, y + h // 2)

    value_size = int(h * 0.42)
    unit_size = _layout_unit_size(value_size)
    room = x + w - pad - (dial[0] + outer + pad)
    while value_size > 8:
        block = (draw.text_width(SAMPLE, value_size)
                 + draw.text_width("%", unit_size))
        if block <= room:
            break
        value_size -= 2
        unit_size = _layout_unit_size(value_size)
    block = draw.text_width(SAMPLE, value_size) + draw.text_width("%",
                                                                 unit_size)
    value_x = x + w - pad - block

    return {
        "record": record,
        "bg": color.rgb(*bg),
        "panel": color.rgb(*panel),
        "accent": color.rgb(*accent),
        "ink": built.ink,
        "dim": built.dim,
        "sweep": _swept(built, dial, outer),
        "arc": shape.arc(vec2(*dial), inner, outer,
                         look.DIAL_FROM, look.DIAL_TO),
        "value_size": value_size,
        "unit_size": unit_size,
        "value_x": value_x,
        "value_y": draw.centre_y(value_size, y + h // 2),
        "unit_y": draw.centre_y(unit_size, y + h // 2),
        "box": (x, y, w, h),
        "shape": shape.rounded_rectangle(rect(x, y, w, h), ui.CORNER()),
        "ring": shape.rounded_rectangle(
            rect(x - gap // 2, y - gap // 2, w + gap, h + gap), look.px(6)),
    }


def _build(theme):
    global _layout, _built_for

    gap = ui.GAP()
    mode = _mode_now()
    left, top, right, bottom = ui.frame()

    tab_h = ui.CONTROL_H()
    rule_h = ui.RULE()
    widest = max(draw.text_width(text, ui.SECTION()) for _k, text in TABS)
    tab_w = widest + look.px(20)
    tabs = []
    for i, (key, text) in enumerate(TABS):
        x = left + i * (tab_w + gap)
        tabs.append({
            "mode": key, "label": text,
            "box": (x, top, tab_w, tab_h),
            "on": shape.rounded_rectangle(rect(x, top, tab_w, tab_h),
                                          0, 0, 0, 0),
            "off": shape.rounded_rectangle(
                rect(x, top, tab_w, tab_h - rule_h), 0, 0, 0, 0),
            "text_y": draw.centre_y(ui.SECTION(), top + (tab_h - rule_h) // 2),
        })
    rule = shape.rectangle(rect(left, top + tab_h - rule_h,
                                right - left, rule_h))

    body_top = top + tab_h + gap
    caption_band = ui.CAPTION_BAND()

    every = themes.records()
    busiest = 1
    for tab, _text in TABS:
        count = len([r for r in every if _in_tab(r, tab)])
        busiest = max(busiest, (count + COLS - 1) // COLS)
    cw, x_of = ui.columns(COLS, gap, left, right)
    per_row = (bottom - body_top - gap * (busiest - 1)) // busiest
    ch = per_row - caption_band
    caption_size = ui.CAPTION_FITTED()

    records = [r for r in every if _in_tab(r, mode)]

    cells = []
    tints = []

    if mode != TINTED:
        for i, record in enumerate(records):
            col, row = i % COLS, i // COLS
            cells.append(_cell(x_of(col), body_top + row * (per_row + gap),
                               cw, ch, record, gap))
    else:
        ordered = ([r for r in records if r["mode"] == "dark"]
                   + [r for r in records if r["mode"] == "light"])
        for i, record in enumerate(ordered):
            cells.append(_cell(x_of(i), body_top, cw, ch, record, gap))

        step = look.px(2)
        tint_rows = len(FAMILIES)
        tint_top = body_top + per_row + gap
        tint_h = (bottom - tint_top - step * (tint_rows - 1)) // tint_rows
        cell_w = (right - left) // len(derive.ACCENT_HUES)
        for row, family in enumerate(FAMILIES):
            palette_row = _accents(family)
            y = tint_top + row * (tint_h + step)
            for at in range(len(derive.ACCENT_HUES)):
                x = left + at * cell_w
                tints.append({
                    "family": family, "index": at, "rgb": palette_row[at],
                    "box": (x, y, cell_w, tint_h),
                    "shape": shape.rectangle(
                        rect(x, y, cell_w - step, tint_h)),
                    "ring": shape.rectangle(
                        rect(x - step, y - step, cell_w - step + step * 2,
                             tint_h + step * 2)),
                })

    for cell in cells:
        x, y, w, h = cell["box"]
        cell["caption"] = themes.label(cell["record"]["name"])
        cell["caption_x"] = x + w // 2
        cell["caption_y"] = draw.centre_y(caption_size,
                                          y + h + caption_band // 2)

    _layout = {
        "tabs": tabs,
        "rule": rule,
        "cells": cells,
        "tints": tints,
        "caption_size": caption_size,
    }
    _built_for = _signature(theme)


def _signature(theme):
    return (theme.key, look.W, look.H, tuple(config.get("tint")),
            config.get("second"), _mode_now())


def _hit(entries, x, y):
    for entry in entries:
        bx, by, bw, bh = entry["box"]
        if bx <= x < bx + bw and by <= y < by + bh:
            return entry
    return None


def on_down(x, y, theme):
    return False


def on_move(x, y):
    return


def on_release():
    return


def on_tap(x, y):
    global _changed, _mode
    if _built_for is None:
        return

    tab = _hit(_layout["tabs"], x, y)
    if tab:
        _mode = tab["mode"]
        return

    cell = _hit(_layout["cells"], x, y)
    if cell:
        _changed |= config.put("theme", cell["record"]["name"])
        return

    tint = _hit(_layout["tints"], x, y)
    if tint:
        config.put("family", tint["family"])
        _changed |= config.put("tint", list(tint["rgb"]))


def render(page, frame, _history, theme):
    if _built_for != _signature(theme):
        _build(theme)

    mode = _mode_now()
    screen.pen = theme.accent
    screen.shape(_layout["rule"])
    for tab in _layout["tabs"]:
        on = tab["mode"] == mode
        screen.pen = theme.accent if on else theme.panel
        screen.shape(tab["on"] if on else tab["off"])
        bx, _by, bw, _bh = tab["box"]
        draw.blit_label(tab["label"], ui.SECTION(),
                        theme.bg if on else theme.dim, bx + bw // 2,
                        tab["text_y"], align=1)

    selected = config.get("theme")
    for cell in _layout["cells"]:
        x, y, w, h = cell["box"]
        if cell["record"]["name"] == selected:
            screen.pen = theme.accent
            screen.shape(cell["ring"])
        screen.pen = cell["bg"]
        screen.shape(cell["shape"])

        screen.pen = cell["sweep"]
        screen.shape(cell["arc"])

        width = draw.blit_label(SAMPLE, cell["value_size"], cell["ink"],
                                cell["value_x"], cell["value_y"])
        draw.blit_label("%", cell["unit_size"], cell["dim"],
                        cell["value_x"] + width, cell["unit_y"])

        screen.pen = cell["accent"]
        screen.rectangle(rect(x, y + h - look.px(4), w, look.px(4)))
        draw.blit_label(cell["caption"], _layout["caption_size"],
                        theme.accent if cell["record"]["name"] == selected
                        else theme.dim,
                        cell["caption_x"], cell["caption_y"], align=1)

    if mode != TINTED:
        return

    family, at = _tint_at()
    for tint in _layout["tints"]:
        if tint["family"] == family and tint["index"] == at:
            screen.pen = theme.ink
            screen.shape(tint["ring"])
        screen.pen = color.rgb(*tint["rgb"])
        screen.shape(tint["shape"])


pages.EXTRA["theme"] = render
