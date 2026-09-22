"""Where the app and the tools meet.

Writing inside the bundle breaks its code signature, and with it the app's
permissions, so everything either side writes lives here. Mounted as /data.

Kept in step with `paths_data` in src/paths_macos.c.
"""

import os
from pathlib import Path

DATA_DIR = Path(os.path.expanduser("~/Library/Application Support/TetraCommand"))


def take_data(argv=()):
    """Return (data directory, the arguments left after `--data DIR` is removed).

    The directory is created if it is not there yet.
    """
    where = DATA_DIR
    rest = []
    argv = list(argv)
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--data" and index + 1 < len(argv):
            where = Path(argv[index + 1])
            index += 2
            continue
        if arg.startswith("--data="):
            where = Path(arg.partition("=")[2])
        else:
            rest.append(arg)
        index += 1
    where.mkdir(parents=True, exist_ok=True)
    return where, rest
