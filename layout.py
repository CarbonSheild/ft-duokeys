"""The keyboard's keys, where they are, and what pressing them sends.

Keys send evdev key codes, so they mean what the desktop's keyboard layout says (the
labels are for a US layout). Positions are in key units (1 = a letter key), measured from
the top left; the panel is WIDTH x HEIGHT units.

Typing does the modifiers so that two hands work together:
  - Hold Shift (Ctrl, Alt, Meta) with one trigger and type with the other: a normal chord.
  - Tap a modifier on its own and it latches: it stays down for the next key, then lets go.
    Tap it again while latched to drop it.
  - The same key from both hands (a double letter typed hand over hand) is pressed again
    for the second hand, not lost.
"""
from dataclasses import dataclass

KEY_ESC, KEY_BACKSPACE, KEY_TAB, KEY_ENTER = 1, 14, 15, 28
KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_RIGHTSHIFT, KEY_LEFTALT = 29, 42, 54, 56
KEY_SPACE, KEY_LEFTMETA, KEY_INSERT, KEY_DELETE = 57, 125, 110, 111
KEY_UP, KEY_LEFT, KEY_RIGHT, KEY_DOWN = 103, 105, 106, 108
MODIFIERS = {KEY_LEFTCTRL, KEY_LEFTSHIFT, KEY_RIGHTSHIFT, KEY_LEFTALT, KEY_LEFTMETA}
SHIFTS = {KEY_LEFTSHIFT, KEY_RIGHTSHIFT}
CLOSE = -1  # not a key code: closes the keyboard
MOVE = -2  # not a key code: the grab bar; the keyboard follows the hand holding it
BAR = 0.6  # the grab bar's row height, above the keys
FROW = 0.8  # the function keys' row height, under the bar
TOP = BAR + FROW  # where the main rows start

GAP = 0.08  # between keys, in units


@dataclass(frozen=True)
class Key:
    label: str
    shifted: str  # label while Shift is down ("" = same as label)
    code: int
    x: float
    y: float
    w: float
    h: float = 1.0

    def contains(self, x, y):
        return self.x <= x < self.x + self.w and self.y <= y < self.y + self.h


def _row(y, spec, h=1.0):
    """Keys from (label, shifted, code, width) left to right."""
    keys, x = [], 0.0
    for label, shifted, code, w in spec:
        keys.append(Key(label, shifted, code, x, y, w, h))
        x += w
    return keys


def _chars(pairs, first_code):
    """One-unit keys for consecutive evdev codes: "aA" -> label a, shifted A."""
    return [(p[0], p[1], first_code + i, 1) for i, p in enumerate(pairs)]


KEYS = (
    [Key("", "", MOVE, 4.5, 0, 6, BAR - GAP)]
    + _row(BAR, [(f"F{n}", "", code, 1) for n, code in
                 zip(range(1, 13), [59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 87, 88])]
           + [("Ins", "", KEY_INSERT, 1.5), ("Del", "", KEY_DELETE, 1.5)], h=FROW)
    + _row(TOP + 0, [("`", "~", 41, 1)] + _chars(["1!", "2@", "3#", "4$", "5%", "6^", "7&", "8*", "9(", "0)", "-_", "=+"], 2)
         + [("Bksp", "", KEY_BACKSPACE, 2)])
    + _row(TOP + 1, [("Tab", "", KEY_TAB, 1.5)] + _chars(["qQ", "wW", "eE", "rR", "tT", "yY", "uU", "iI", "oO", "pP", "[{", "]}"], 16)
           + [("\\", "|", 43, 1.5)])
    + _row(TOP + 2, [("Esc", "", KEY_ESC, 1.75)] + _chars(["aA", "sS", "dD", "fF", "gG", "hH", "jJ", "kK", "lL", ";:", "'\""], 30)
           + [("Enter", "", KEY_ENTER, 2.25)])
    + _row(TOP + 3, [("Shift", "", KEY_LEFTSHIFT, 2.25)] + _chars(["zZ", "xX", "cC", "vV", "bB", "nN", "mM", ",<", ".>", "/?"], 44)
           + [("Shift", "", KEY_RIGHTSHIFT, 2.75)])
    + _row(TOP + 4, [("Ctrl", "", KEY_LEFTCTRL, 1.5), ("Alt", "", KEY_LEFTALT, 1.25), ("Meta", "", KEY_LEFTMETA, 1.25),
               ("", "", KEY_SPACE, 5), ("←", "", KEY_LEFT, 1), ("↑", "", KEY_UP, 1), ("↓", "", KEY_DOWN, 1),
               ("→", "", KEY_RIGHT, 1), ("Close", "", CLOSE, 2)])
)
WIDTH = 15.0
HEIGHT = 5.0 + TOP


def key_at(x, y):
    """The key under (x, y) in units, or None (off the panel or in a gap)."""
    for k in KEYS:
        if k.contains(x, y):
            return k
    return None


class Typing:
    """Turns key presses and releases from either hand into key events.

    press(hand, key) and release(hand) return a list of (code, value) to send, value 1
    for down and 0 for up. CLOSE and MOVE give no events: the caller closes the keyboard,
    or carries it.
    """

    def __init__(self):
        self.held = {}  # hand -> the Key that hand's trigger holds
        self.down = {}  # code -> number of hands holding it (keys sent down)
        self.mod_used = {}  # modifier code held by a hand -> another key was typed during the hold
        self.latched = set()  # modifier codes left down for the next key

    def shift(self):
        """Whether Shift is down, for the labels."""
        return any(self.down.get(c) for c in SHIFTS) or bool(self.latched & SHIFTS)

    def active_mods(self):
        """Modifier codes that are down (held or latched), for drawing."""
        return {c for c in MODIFIERS if self.down.get(c)} | self.latched

    def press(self, hand, key):
        out = []
        if hand in self.held:
            out += self.release(hand)
        self.held[hand] = key
        code = key.code
        if code in (CLOSE, MOVE):
            return out
        if code in MODIFIERS:
            if code in self.latched:  # a second tap drops the latch
                self.latched.discard(code)
                self.down.pop(code, None)  # so its release sends nothing more
                out.append((code, 0))
                return out
            self.mod_used[code] = False
            if not self.down.get(code):
                out.append((code, 1))
            self.down[code] = self.down.get(code, 0) + 1
            return out
        for m in self.mod_used:
            self.mod_used[m] = True
        if self.down.get(code):
            out.append((code, 0))  # the other hand has it: press it again
        out.append((code, 1))
        self.down[code] = self.down.get(code, 0) + 1
        return out

    def release(self, hand):
        key = self.held.pop(hand, None)
        if key is None or key.code in (CLOSE, MOVE):
            return []
        code, out = key.code, []
        if code in MODIFIERS:
            if not self.down.get(code):
                return out  # this press only dropped a latch
            self.down[code] -= 1
            if self.down[code]:
                return out  # the other hand still holds it
            if self.mod_used.pop(code, True):
                del self.down[code]
                out.append((code, 0))
            else:
                self.down[code] = 0
                self.latched.add(code)  # tapped alone: stays down for the next key
            return out
        self.down[code] -= 1
        if not self.down[code]:
            del self.down[code]
            out.append((code, 0))
            for m in sorted(self.latched):
                out.append((m, 0))
                self.down.pop(m, None)
            self.latched.clear()
        return out

    def release_all(self):
        """Everything up: the keyboard is closing, or input was lost."""
        out = []
        for hand in list(self.held):
            out += self.release(hand)
        for code in sorted(set(self.down) | self.latched):
            out.append((code, 0))  # latched modifiers (a released hand may have just latched one)
        self.down.clear()
        self.latched.clear()
        self.mod_used.clear()
        return out
