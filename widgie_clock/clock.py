"""Analog face geometry from the Windows Widgie Clock, in a 260px design space."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime

import cairo

import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

DESIGN = 260.0
CENTER = DESIGN / 2.0


@dataclass(frozen=True)
class HandAngles:
    hour: float
    minute: float
    second: float


def hand_angles(moment: datetime) -> HandAngles:
    """Match WidgieClock.Services.ClockService.GetAngles.

    Hands sweep continuously. Noon and midnight are 0 degrees, and angles
    increase clockwise, which is Cairo's positive rotation in a y-down space.
    """

    total_seconds = (
        moment.hour * 3600
        + moment.minute * 60
        + moment.second
        + moment.microsecond / 1_000_000
    )
    second = total_seconds % 60.0
    minute = (total_seconds / 60.0) % 60.0
    hour = (total_seconds / 3600.0) % 12.0
    return HandAngles(hour * 30.0, minute * 6.0, second * 6.0)


def _argb(value: int) -> tuple[float, float, float, float]:
    alpha = ((value >> 24) & 0xFF) / 255.0
    red = ((value >> 16) & 0xFF) / 255.0
    green = ((value >> 8) & 0xFF) / 255.0
    blue = (value & 0xFF) / 255.0
    return red, green, blue, alpha


def _ellipse(cr: cairo.Context, x: float, y: float, width: float, height: float) -> None:
    cr.new_path()
    cr.save()
    cr.translate(x + width / 2.0, y + height / 2.0)
    cr.scale(max(width, 0.01) / 2.0, max(height, 0.01) / 2.0)
    cr.arc(0, 0, 1, 0, math.tau)
    cr.restore()


def _round_rect(
    cr: cairo.Context,
    x: float,
    y: float,
    width: float,
    height: float,
    radius: float,
) -> None:
    radius = min(radius, width / 2.0, height / 2.0)
    cr.new_path()
    cr.arc(x + width - radius, y + radius, radius, -math.pi / 2, 0)
    cr.arc(x + width - radius, y + height - radius, radius, 0, math.pi / 2)
    cr.arc(x + radius, y + height - radius, radius, math.pi / 2, math.pi)
    cr.arc(x + radius, y + radius, radius, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _draw_ticks(cr: cairo.Context) -> None:
    cr.set_source_rgba(0, 0, 0, 1)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    for index in range(60):
        hour_mark = index % 5 == 0
        angle = math.radians(index * 6.0)
        outer = 110.0
        inner = 96.0 if hour_mark else 104.0
        cr.set_line_width(2.0 if hour_mark else 1.0)
        cr.new_path()
        cr.move_to(CENTER + math.sin(angle) * outer, CENTER - math.cos(angle) * outer)
        cr.line_to(CENTER + math.sin(angle) * inner, CENTER - math.cos(angle) * inner)
        cr.stroke()


def _draw_numeral(cr: cairo.Context, text: str, x: float, y: float, width: float) -> None:
    layout = PangoCairo.create_layout(cr)
    description = Pango.FontDescription()
    description.set_family("Noto Sans")
    description.set_weight(Pango.Weight.BOLD)
    # WPF FontSize is a 96dpi pixel size, not a point size.
    description.set_absolute_size(28 * Pango.SCALE)
    layout.set_font_description(description)
    layout.set_width(int(width * Pango.SCALE))
    layout.set_alignment(Pango.Alignment.CENTER)
    layout.set_text(text, -1)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.move_to(x, y)
    PangoCairo.show_layout(cr, layout)


def _rotated(cr: cairo.Context, degrees: float):
    cr.save()
    cr.translate(CENTER, CENTER)
    cr.rotate(math.radians(degrees))
    cr.translate(-CENTER, -CENTER)
    return cr


def _draw_hour(cr: cairo.Context, degrees: float) -> None:
    _rotated(cr, degrees)
    cr.new_path()
    cr.move_to(130, 130)
    cr.line_to(123, 118)
    cr.line_to(130, 58)
    cr.line_to(137, 118)
    cr.close_path()
    cr.set_source_rgba(0, 0, 0, 1)
    cr.fill()
    cr.restore()


def _draw_minute(cr: cairo.Context, degrees: float) -> None:
    _rotated(cr, degrees)
    cr.new_path()
    cr.move_to(130, 130)
    cr.line_to(126, 116)
    cr.line_to(130, 38)
    cr.line_to(134, 116)
    cr.close_path()
    cr.set_source_rgba(0, 0, 0, 1)
    cr.fill()
    cr.restore()


def _draw_second(cr: cairo.Context, degrees: float) -> None:
    _rotated(cr, degrees)
    cr.set_source_rgba(0, 0, 0, 1)
    _round_rect(cr, 129.25, 36, 1.5, 106, 0.75)
    cr.fill()
    _round_rect(cr, 128.75, 142, 2.5, 26, 1.0)
    cr.fill()
    _ellipse(cr, 126.5, 126.5, 7, 7)
    cr.fill()
    cr.restore()


def _draw_sheen(cr: cairo.Context) -> None:
    gradient = cairo.LinearGradient(130, 28, 130, 112)
    gradient.add_color_stop_rgba(0, 1, 1, 1, 0x40 / 255)
    gradient.add_color_stop_rgba(1, 1, 1, 1, 0)
    cr.set_source(gradient)
    _ellipse(cr, 30, 28, 200, 84)
    cr.fill()


def draw_clock(
    cr: cairo.Context,
    width: int,
    height: int,
    angles: HandAngles,
    background: tuple[float, float, float, float] | None = None,
) -> None:
    """Paint the face into width x height. Corners outside the bezel stay transparent."""

    if background is not None:
        cr.set_source_rgba(*background)
        cr.paint()

    scale = min(width, height) / DESIGN
    cr.save()
    cr.translate((width - DESIGN * scale) / 2.0, (height - DESIGN * scale) / 2.0)
    cr.scale(scale, scale)
    cr.set_antialias(cairo.ANTIALIAS_BEST)

    _ellipse(cr, 0, 0, 260, 260)
    cr.set_source_rgba(*_argb(0xFF111111))
    cr.fill()

    _ellipse(cr, 0, 0, 260, 260)
    cr.set_source_rgba(*_argb(0x33FFFFFF))
    cr.set_line_width(1.5)
    cr.stroke()

    _ellipse(cr, 6, 6, 248, 248)
    cr.set_source_rgba(*_argb(0x44000000))
    cr.set_line_width(1.0)
    cr.stroke()

    focal_x = 12 + 0.38 * 236
    focal_y = 12 + 0.32 * 236
    dial = cairo.RadialGradient(focal_x, focal_y, 0, CENTER, CENTER, 0.8 * 118)
    dial.add_color_stop_rgba(0, *_argb(0xFFF7F2E8))
    dial.add_color_stop_rgba(0.65, *_argb(0xFFECE4D6))
    dial.add_color_stop_rgba(1, *_argb(0xFFD9CFBE))
    _ellipse(cr, 12, 12, 236, 236)
    cr.set_source(dial)
    cr.fill()

    _ellipse(cr, 12, 12, 236, 236)
    cr.set_source_rgba(*_argb(0x18000000))
    cr.set_line_width(1.5)
    cr.stroke()

    _draw_ticks(cr)
    _draw_numeral(cr, "12", 106, 30, 48)
    _draw_numeral(cr, "3", 192, 110, 36)
    _draw_numeral(cr, "6", 112, 188, 36)
    _draw_numeral(cr, "9", 32, 110, 36)

    _draw_hour(cr, angles.hour)
    _draw_minute(cr, angles.minute)
    _draw_second(cr, angles.second)

    _ellipse(cr, 123, 123, 14, 14)
    cr.set_source_rgba(0, 0, 0, 1)
    cr.fill()
    _ellipse(cr, 127, 127, 6, 6)
    cr.set_source_rgba(*_argb(0xFF333333))
    cr.fill()

    _draw_sheen(cr)
    cr.restore()


def render_png(
    path: str,
    size: int,
    moment: datetime,
    background: tuple[float, float, float, float] | None = None,
) -> None:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    draw_clock(cairo.Context(surface), size, size, hand_angles(moment), background)
    surface.write_to_png(path)
