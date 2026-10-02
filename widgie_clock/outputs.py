"""Monitor geometry from GDK, plus Hyprland reserved insets when hyprctl is available."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from gi.repository import Gdk


@dataclass
class OutputInfo:
    connector: str
    width: int
    height: int
    reserved: tuple[int, int, int, int]
    monitor: Gdk.Monitor
    focused: bool


def _hypr_monitors() -> dict[str, dict]:
    try:
        raw = subprocess.check_output(
            ["hyprctl", "monitors", "-j"],
            text=True,
            timeout=1,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return {}

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    found: dict[str, dict] = {}
    if not isinstance(payload, list):
        return found
    for item in payload:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        reserved = item.get("reserved") or [0, 0, 0, 0]
        if not isinstance(reserved, list) or len(reserved) != 4:
            reserved = [0, 0, 0, 0]
        try:
            scale = float(item.get("scale") or 1)
            width = int(item.get("width") or 0)
        except (TypeError, ValueError):
            scale, width = 1.0, 0
        found[str(item["name"])] = {
            "reserved": tuple(int(value) for value in reserved),
            "scale": scale or 1.0,
            "width": width,
            "focused": bool(item.get("focused")),
        }
    return found


def _reserved_for_gdk(info: dict | None, gdk_width: int) -> tuple[int, int, int, int]:
    """Hyprland reports reserved as left, top, right, bottom in layout pixels."""

    if not info:
        return (0, 0, 0, 0)
    reserved = info["reserved"]
    scale = info["scale"] or 1.0
    logical_width = info["width"] / scale if info["width"] else gdk_width
    if abs(gdk_width - logical_width) <= abs(gdk_width - info["width"]):
        return reserved
    return tuple(int(round(value * scale)) for value in reserved)


def list_outputs() -> list[OutputInfo]:
    display = Gdk.Display.get_default()
    if display is None:
        return []
    hypr = _hypr_monitors()
    model = display.get_monitors()
    outputs: list[OutputInfo] = []
    for index in range(model.get_n_items()):
        monitor = model.get_item(index)
        geometry = monitor.get_geometry()
        connector = monitor.get_connector() or f"monitor-{index}"
        info = hypr.get(connector)
        outputs.append(
            OutputInfo(
                connector=connector,
                width=int(geometry.width),
                height=int(geometry.height),
                reserved=_reserved_for_gdk(info, int(geometry.width)),
                monitor=monitor,
                focused=bool(info and info["focused"]),
            )
        )
    return outputs


def choose_output(outputs: list[OutputInfo], connector: str | None) -> OutputInfo | None:
    if not outputs:
        return None
    if connector:
        for output in outputs:
            if output.connector == connector:
                return output
    for output in outputs:
        if output.focused:
            return output
    return outputs[0]
