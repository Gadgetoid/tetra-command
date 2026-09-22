"""Step macro generators and drive the HID layer."""

import hid
from keys import DO_NOTHING


class Runner:
    def __init__(self):
        self.stack = []
        self._last = None
        self._holding = False

    def start(self, macro, hold=False):
        """Queue a macro; `hold` runs it only while a finger stays down."""
        if macro is None:
            return
        self._holding = hold
        self.stack.insert(0, macro() if callable(macro) else macro)

    def release(self):
        """End a held macro on finger lift."""
        if self._holding:
            self.cancel()

    @property
    def busy(self):
        return bool(self.stack)

    def cancel(self):
        self.stack.clear()
        self._last = None
        self._holding = False
        hid.release_all()

    def step(self):
        """Advance one frame and return the keys held."""
        if not self.stack:
            return ()

        keys = []
        macro = self.stack[0]
        try:
            value = next(macro)
        except StopIteration:
            self.stack.pop(0)
            value = None
            keys.append(0)

        if value is not None:
            while True:
                try:
                    inner = next(value)
                except TypeError:
                    break
                except StopIteration:
                    value = DO_NOTHING
                    break
                self.stack.insert(0, value)
                value = inner

            if isinstance(value, (list, tuple)):
                keys.extend(value)
            elif callable(value):
                self.stack.insert(0, value())
            elif value > DO_NOTHING:
                keys.append(value)
            else:
                return self._resend()

        held = tuple(k for k in keys if k)
        self._last = held
        hid.send_keys(held)
        return held

    def _resend(self):
        held = self._last or ()
        hid.send_keys(held)
        return held
