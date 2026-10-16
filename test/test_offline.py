#!/usr/bin/env python3
"""Offline tests: no SteamVR, no headset, no /dev/uinput.  python3 test/test_offline.py"""
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import hands  # noqa: E402
import layout  # noqa: E402

I = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]]


def at(x, y, z):
    """A laser at (x, y, z) aiming along -z (the identity orientation)."""
    return [[1, 0, 0, x], [0, 1, 0, y], [0, 0, 1, z]]


def key(label):
    return next(k for k in layout.KEYS if k.label == label)


class Rays(unittest.TestCase):
    def test_hit_centre_and_corner(self):
        hit = hands.ray_hit(I, 0.6, 0.2, at(0, 0, 0.5))
        self.assertAlmostEqual(hit[0], 0.3)
        self.assertAlmostEqual(hit[1], 0.1)
        self.assertAlmostEqual(hit[2], 0.5)
        hit = hands.ray_hit(I, 0.6, 0.2, at(-0.3, 0.1, 0.5))  # top left
        self.assertAlmostEqual(hit[0], 0.0)
        self.assertAlmostEqual(hit[1], 0.0)

    def test_behind_or_away(self):
        self.assertIsNone(hands.ray_hit(I, 0.6, 0.2, at(0, 0, -0.5)))
        away = [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, -1, 0.5]]  # aims along +z, away from the panel
        self.assertIsNone(hands.ray_hit(I, 0.6, 0.2, away))

    def test_inside_margin(self):
        hit = hands.ray_hit(I, 0.6, 0.2, at(0.31, 0, 0.5))
        self.assertFalse(hands.inside(hit, 0.6, 0.2))
        self.assertTrue(hands.inside(hit, 0.6, 0.2, 0.015))

    def test_tilted_tip(self):
        # The Frame's tip aims 40 degrees below the pose's forward.
        c, s = math.cos(math.radians(40)), math.sin(math.radians(40))
        tip = [[1, 0, 0, 0], [0, c, s, 0], [0, -s, c, 0]]
        laser = hands.mul(at(0, 0, 1), tip)
        d = hands.col(laser, 2)
        self.assertAlmostEqual(-d[1], -s, places=6)  # it aims downward
        hit = hands.ray_hit([[1, 0, 0, 0], [0, 1, 0, -math.tan(math.radians(40))], [0, 0, 1, 0]], 0.6, 0.2, laser)
        self.assertAlmostEqual(hit[0], 0.3)
        self.assertAlmostEqual(hit[1], 0.1)


class Takeovers(unittest.TestCase):
    W, H = 0.6, 0.2
    ON, EDGE, OFF = (0.3, 0.1, 0.5), (0.61, 0.1, 0.5), (0.8, 0.1, 0.5)

    def test_takes_and_gives_back_with_trigger_up(self):
        t = hands.Takeover()
        self.assertTrue(t.update(self.ON, self.W, self.H, False))
        self.assertFalse(t.update(self.OFF, self.W, self.H, False))

    def test_never_switches_while_trigger_held(self):
        t = hands.Takeover()
        self.assertFalse(t.update(self.ON, self.W, self.H, True))  # arrived with the trigger held
        self.assertTrue(t.update(self.ON, self.W, self.H, False))
        self.assertTrue(t.update(self.OFF, self.W, self.H, True))  # left while held: stays ours
        self.assertFalse(t.update(self.OFF, self.W, self.H, False))

    def test_grown_edge_once_taken(self):
        t = hands.Takeover()
        self.assertFalse(t.update(self.EDGE, self.W, self.H, False))  # 1 cm out: not yet
        t.update(self.ON, self.W, self.H, False)
        self.assertTrue(t.update(self.EDGE, self.W, self.H, False))  # inside the grown edge

    def test_closing(self):
        t = hands.Takeover()
        t.update(self.ON, self.W, self.H, False)
        self.assertTrue(t.update(self.ON, self.W, self.H, True, want=False))  # Close key, trigger held
        self.assertFalse(t.update(self.ON, self.W, self.H, False, want=False))


class Placement(unittest.TestCase):
    def test_in_front_below_and_facing(self):
        head = [[1, 0, 0, 0], [0, 1, 0, 1.6], [0, 0, 1, 0]]  # looking along -z
        p = hands.placement(head)
        self.assertAlmostEqual(p[0][3], 0)
        self.assertAlmostEqual(p[1][3], 1.6 - 0.38)
        self.assertAlmostEqual(p[2][3], -0.55)
        n = hands.col(p, 2)  # its front faces back toward the head, and up
        self.assertGreater(n[2], 0)
        self.assertGreater(n[1], 0)

    def test_yaw_follows_head(self):
        head = [[0, 0, 1, 0], [0, 1, 0, 1.6], [-1, 0, 0, 0]]  # turned to look along -x
        p = hands.placement(head)
        self.assertAlmostEqual(p[0][3], -0.55)
        self.assertGreater(hands.col(p, 2)[0], 0)


    def test_remembered_spot_follows_the_head(self):
        head = [[1, 0, 0, 0.2], [0, 1, 0, 1.6], [0, 0, 1, 0.1]]
        put = hands.placement(head, [[1, 0, 0, 0.1], [0, 1, 0, -0.5], [0, 0, 1, -0.7]])
        off = hands.remember(head, put)
        turned = [[0, 0, 1, 0], [0, 1, 0, 1.6], [-1, 0, 0, 0]]  # facing -x now
        p = hands.placement(turned, off)
        self.assertAlmostEqual(p[0][3], -0.7)  # 0.7 ahead
        self.assertAlmostEqual(p[1][3], 1.1)  # 0.5 below
        self.assertAlmostEqual(p[2][3], -0.1)  # 0.1 to the right


class Layout(unittest.TestCase):
    def test_rows_fit(self):
        for k in layout.KEYS:
            self.assertLessEqual(k.x + k.w, layout.WIDTH + 1e-9, k)
            self.assertLessEqual(k.y + k.h, layout.HEIGHT + 1e-9, k)

    def test_key_at(self):
        self.assertEqual(layout.key_at(0.5, layout.TOP + 0.5).label, "`")
        self.assertEqual(layout.key_at(1.75 + 0.5, layout.TOP + 2.5).label, "a")
        self.assertEqual(layout.key_at(11.5, layout.BAR + 0.4).label, "F12")
        self.assertEqual(layout.key_at(11.5, layout.BAR + 0.4).code, 88)
        self.assertEqual(layout.key_at(7.5, 0.2).code, layout.MOVE)
        self.assertIsNone(layout.key_at(0.5, 0.2))  # beside the bar
        self.assertIsNone(layout.key_at(-1, 0))


class TypingTests(unittest.TestCase):
    def test_plain_key(self):
        t = layout.Typing()
        self.assertEqual(t.press("left", key("a")), [(30, 1)])
        self.assertEqual(t.release("left"), [(30, 0)])

    def test_held_shift_chord(self):
        t = layout.Typing()
        self.assertEqual(t.press("left", key("Shift")), [(42, 1)])
        self.assertEqual(t.press("right", key("a")), [(30, 1)])
        self.assertEqual(t.release("right"), [(30, 0)])
        self.assertEqual(t.press("right", key("s")), [(31, 1)])  # still held: still shifted
        self.assertEqual(t.release("right"), [(31, 0)])
        self.assertEqual(t.release("left"), [(42, 0)])
        self.assertFalse(t.shift())

    def test_tapped_shift_latches_for_one_key(self):
        t = layout.Typing()
        t.press("left", key("Shift"))
        self.assertEqual(t.release("left"), [])
        self.assertTrue(t.shift())
        self.assertEqual(t.press("right", key("a")), [(30, 1)])
        self.assertEqual(t.release("right"), [(30, 0), (42, 0)])
        self.assertFalse(t.shift())

    def test_second_tap_drops_latch(self):
        t = layout.Typing()
        t.press("left", key("Shift"))
        t.release("left")
        self.assertEqual(t.press("left", key("Shift")), [(42, 0)])
        self.assertEqual(t.release("left"), [])
        self.assertFalse(t.shift())
        self.assertEqual(t.active_mods(), set())

    def test_same_key_both_hands(self):
        t = layout.Typing()
        self.assertEqual(t.press("left", key("l")), [(38, 1)])
        self.assertEqual(t.press("right", key("l")), [(38, 0), (38, 1)])
        self.assertEqual(t.release("left"), [])
        self.assertEqual(t.release("right"), [(38, 0)])

    def test_release_all(self):
        t = layout.Typing()
        t.press("left", key("Ctrl"))
        t.press("right", key("c"))
        out = t.release_all()
        self.assertCountEqual(out, [(46, 0), (29, 0)])
        self.assertEqual(t.down, {})

    def test_release_all_latched(self):
        t = layout.Typing()
        t.press("left", key("Alt"))
        t.release("left")
        self.assertEqual(t.release_all(), [(56, 0)])

    def test_close_sends_nothing(self):
        t = layout.Typing()
        self.assertEqual(t.press("left", key("Close")), [])
        self.assertEqual(t.release("left"), [])


class Carry(unittest.TestCase):
    def test_inverse(self):
        c, s_ = math.cos(0.7), math.sin(0.7)
        m = [[c, -s_, 0, 1], [s_, c, 0, 2], [0, 0, 1, 3]]
        back = hands.mul(m, hands.inverse(m))
        for i in range(3):
            for j in range(4):
                self.assertAlmostEqual(back[i][j], I[i][j])

    def test_move_key_types_nothing(self):
        t = layout.Typing()
        bar = next(k for k in layout.KEYS if k.code == layout.MOVE)
        self.assertEqual(t.press("left", bar), [])
        self.assertEqual(t.release("left"), [])


class LaserPose(unittest.TestCase):
    def test_axes(self):
        p = hands.laser_pose((0, 0, 0), (0, 0, -1), (0, 1, 0), 1)
        y, z = hands.col(p, 1), hands.col(p, 2)
        self.assertAlmostEqual(y[2], -1)
        self.assertAlmostEqual(z[1], 1)  # faces the head, above
        self.assertAlmostEqual(p[2][3], -0.5)


if __name__ == "__main__":
    unittest.main()
