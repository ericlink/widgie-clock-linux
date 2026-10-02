"""Where the face sits on a monitor. Coordinates are layer-shell margins."""

from __future__ import annotations

EDGE_MARGIN = 24
MIN_VISIBLE = 24


def default_origin(
    width: int,
    height: int,
    size: int,
    reserved: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> tuple[int, int]:
    """Top-right inset, matching the Windows default of 24px from the work area.

    Layer-shell margins sit outside other surfaces' exclusive zones, so a bar
    is already skipped by the compositor. ``reserved`` is accepted so callers
    can pass monitor insets without changing this inset.
    """

    del height, reserved
    return (width - size - EDGE_MARGIN, EDGE_MARGIN)


def clamp_origin(
    left: float,
    top: float,
    size: int,
    width: int,
    height: int,
    min_visible: int = MIN_VISIBLE,
) -> tuple[int, int]:
    """Keep at least ``min_visible`` pixels on the output so a locked face can be found."""

    left_i = int(round(left))
    top_i = int(round(top))
    if width <= min_visible:
        left_i = 0
    else:
        left_i = min(max(left_i, -(size - min_visible)), width - min_visible)
    if height <= min_visible:
        top_i = 0
    else:
        top_i = min(max(top_i, -(size - min_visible)), height - min_visible)
    return left_i, top_i
