"""Draws the keyboard panel (Pillow).

The plain keys are drawn once per Shift state and cached; each frame that something
changes only the hovered, pressed and latched keys are drawn over a copy.
"""
import math
import os

from PIL import Image, ImageDraw, ImageFont

import layout

PX = 96  # pixels per key unit
MARGIN = 16
SIZE = (int(layout.WIDTH * PX) + 2 * MARGIN, int(layout.HEIGHT * PX) + 2 * MARGIN)

BG = (14, 15, 18, 235)
KEY = (52, 56, 66, 255)
KEY_SPECIAL = (38, 41, 49, 255)
TEXT = (232, 234, 238, 255)
TEXT_DIM = (160, 166, 178, 255)
MOD_ON = (70, 110, 190, 255)
HAND = {"left": (64, 150, 255), "right": (255, 150, 64)}  # hover and press tint per hand

_FONTS = ["/usr/share/fonts/noto/NotoSans-Medium.ttf", "/usr/share/fonts/noto/NotoSans-Regular.ttf",
          "/usr/share/fonts/TTF/DejaVuSans.ttf"]


def _font(size):
    for path in _FONTS:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size)


FONT, FONT_SMALL = _font(40), _font(28)


def rect(key):
    """A key's rectangle in pixels."""
    g = layout.GAP / 2
    return (MARGIN + (key.x + g) * PX, MARGIN + (key.y + g) * PX,
            MARGIN + (key.x + key.w - g) * PX, MARGIN + (key.y + key.h - g) * PX)


# Arrow keys are drawn as triangles: the label fonts have no arrow glyphs. Points for one
# pointing right, around (0, 0), 1 = half its length; turned per key.
_ARROW = {layout.KEY_RIGHT: 0, layout.KEY_DOWN: 90, layout.KEY_LEFT: 180, layout.KEY_UP: 270}


def _draw_arrow(d, key, deg):
    x0, y0, x1, y1 = rect(key)
    cx, cy, r = (x0 + x1) / 2, (y0 + y1) / 2, 16
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    pts = [(1, 0), (-0.7, -0.9), (-0.7, 0.9)]
    d.polygon([(cx + r * (x * c - y * s), cy + r * (x * s + y * c)) for x, y in pts], fill=TEXT)


def _draw_key(d, key, fill, shift):
    if key.code == layout.MOVE:  # the grab bar: a pill with a grip line
        x0, y0, x1, y1 = rect(key)
        d.rounded_rectangle(rect(key), radius=int((y1 - y0) / 2), fill=fill)
        cy = (y0 + y1) / 2
        d.line(((x0 + x1) / 2 - 60, cy, (x0 + x1) / 2 + 60, cy), fill=TEXT_DIM, width=6)
        return
    d.rounded_rectangle(rect(key), radius=10, fill=fill)
    if key.code in _ARROW:
        return _draw_arrow(d, key, _ARROW[key.code])
    label = key.shifted if shift and key.shifted else key.label
    if shift and not key.shifted and len(label) == 1:
        label = label.upper()
    font = FONT if len(label) <= 1 else FONT_SMALL
    x0, y0, x1, y1 = rect(key)
    d.text(((x0 + x1) / 2, (y0 + y1) / 2), label, fill=TEXT if len(label) <= 1 else TEXT_DIM,
           font=font, anchor="mm")


_base = {}


def _plain(shift):
    if shift not in _base:
        img = Image.new("RGBA", SIZE, BG)
        d = ImageDraw.Draw(img)
        for k in layout.KEYS:
            _draw_key(d, k, KEY if len(k.label) <= 1 and k.code != layout.KEY_SPACE else KEY_SPECIAL, shift)
        _base[shift] = img
    return _base[shift]


def _mix(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


def image(shift, mods, hover, pressed):
    """mods: modifier codes that are down; hover and pressed: {hand: Key}. A Pillow image."""
    img = _plain(shift).copy()
    d = ImageDraw.Draw(img)
    for k in layout.KEYS:
        if k.code in mods:
            _draw_key(d, k, MOD_ON, shift)
    for hand, k in hover.items():
        if k is not None and pressed.get(hand) is not k:
            _draw_key(d, k, _mix(KEY, HAND[hand], 0.35), shift)
    for hand, k in pressed.items():
        if k is not None:
            _draw_key(d, k, _mix(KEY, HAND[hand], 0.8), shift)
    return img


def draw(shift, mods, hover, pressed):
    """The same as RGBA bytes."""
    return image(shift, mods, hover, pressed).tobytes()


def dot(hand, size=32):
    """A cursor dot for one hand: a filled circle with a dark rim."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((1, 1, size - 2, size - 2), fill=(20, 20, 20, 200))
    d.ellipse((5, 5, size - 6, size - 6), fill=HAND[hand] + (255,))
    return img.tobytes(), size, size


def beam(hand, w=4, h=64):
    """A laser texture: the hand's colour, fading out toward the controller. The beam's +y
    points at the panel (hands.laser_pose), and a texture's top row is an overlay's +y end."""
    img = Image.new("RGBA", (w, h))
    for y in range(h):
        a = int(40 + 160 * (h - 1 - y) / (h - 1))
        for x in range(w):
            img.putpixel((x, y), HAND[hand] + (a,))
    return img.tobytes(), w, h


def highlight(hand, pressed, size=64):
    """A key highlight for one hand, laid over the key as its own overlay: the hand's tint,
    see-through so the label shows, stronger while pressed."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 8,
                        fill=HAND[hand] + ((170,) if pressed else (90,)))
    return img.tobytes(), size, size


def mod_mark(size=64):
    """A held or latched modifier's light, laid over its key like a highlight."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((0, 0, size - 1, size - 1), radius=size // 8, fill=MOD_ON[:3] + (150,))
    return img.tobytes(), size, size
