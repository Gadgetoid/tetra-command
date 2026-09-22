"""Persist settings to a JSON file in the writable data directory."""

import json

import derive

PATH = "/data/config.json"

DEFAULTS = {
    "theme": "dark",
    "tint": list(derive.accents()[6]),
    "family": "normal",
    "second": "same",
    "face": "amsterdam",
    "clock_themed": False,
}

_state = None


def load():
    global _state
    if _state is None:
        _state = {}
        for key, value in DEFAULTS.items():
            _state[key] = list(value) if isinstance(value, list) else value
        try:
            with open(PATH) as handle:
                stored = json.load(handle)
        except Exception:
            stored = {}
        for key, value in stored.items():
            if key in DEFAULTS:
                _state[key] = value
    return _state


def get(key):
    return load().get(key)


def put(key, value):
    state = load()
    if state.get(key) == value:
        return False
    state[key] = value
    save()
    return True


def save():
    try:
        with open(PATH, "w") as handle:
            json.dump(load(), handle)
        return True
    except Exception as error:
        print("config: could not write", PATH, error)
        return False
