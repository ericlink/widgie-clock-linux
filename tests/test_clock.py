import struct
import unittest
from datetime import datetime

import cairo

from widgie_clock.clock import DESIGN, draw_clock, hand_angles


def _pixel(surface: cairo.ImageSurface, x: int, y: int) -> tuple[int, int, int, int]:
    word = struct.unpack_from("=I", surface.get_data(), (y * surface.get_width() + x) * 4)[0]
    alpha = (word >> 24) & 255
    red = (word >> 16) & 255
    green = (word >> 8) & 255
    blue = word & 255
    return red, green, blue, alpha


class HandAngleTests(unittest.TestCase):
    def test_midnight_is_zero(self) -> None:
        angles = hand_angles(datetime(2026, 1, 1, 0, 0, 0))
        self.assertEqual(angles, hand_angles(datetime(2026, 1, 1, 12, 0, 0)))
        self.assertEqual((angles.hour, angles.minute, angles.second), (0.0, 0.0, 0.0))

    def test_three_oclock(self) -> None:
        angles = hand_angles(datetime(2026, 1, 1, 3, 0, 0))
        self.assertEqual(angles.hour, 90.0)
        self.assertEqual(angles.minute, 0.0)
        self.assertEqual(angles.second, 0.0)

    def test_continuous_sweep(self) -> None:
        angles = hand_angles(datetime(2026, 1, 1, 15, 30, 30))
        self.assertAlmostEqual(angles.second, 180.0)
        self.assertAlmostEqual(angles.minute, 183.0)
        self.assertAlmostEqual(angles.hour, 105.25)

    def test_fractional_second(self) -> None:
        angles = hand_angles(datetime(2026, 1, 1, 0, 0, 0, 500_000))
        self.assertAlmostEqual(angles.second, 3.0)


class FaceTests(unittest.TestCase):
    def _render(self, moment: datetime) -> cairo.ImageSurface:
        size = int(DESIGN)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
        draw_clock(cairo.Context(surface), size, size, hand_angles(moment))
        surface.flush()
        return surface

    def test_corners_are_transparent_and_noon_hand_points_up(self) -> None:
        surface = self._render(datetime(2026, 1, 1, 12, 0, 0))
        self.assertEqual(_pixel(surface, 0, 0)[3], 0)
        self.assertEqual(_pixel(surface, 259, 0)[3], 0)

        # Wide part of the minute hand, below the "12" and above the pinion.
        up = _pixel(surface, 130, 100)
        self.assertLess(up[0], 40, up)
        self.assertGreater(up[3], 200)

        # Open dial at 3 o'clock, inside the numeral and the tick ring.
        dial = _pixel(surface, 180, 130)
        self.assertGreater(dial[0], 180, dial)
        self.assertGreater(dial[1], 170, dial)

    def test_quarter_past_three_points_right(self) -> None:
        # 3:15:15 puts hour, minute, and second all near 3 o'clock.
        surface = self._render(datetime(2026, 1, 1, 3, 15, 15))
        right = _pixel(surface, 180, 130)
        up = _pixel(surface, 130, 100)
        self.assertLess(right[0], 40, right)
        self.assertGreater(up[0], 180, up)


if __name__ == "__main__":
    unittest.main()
