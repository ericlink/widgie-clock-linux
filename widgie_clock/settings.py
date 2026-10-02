"""JSON settings, with the same bounds and legacy-size migration as the Windows app."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_SIZE = 130.0
LEGACY_DEFAULT_SIZE = 260.0
MIN_SIZE = 80.0
MAX_SIZE = 600.0


@dataclass
class AppSettings:
    left: float | None = None
    top: float | None = None
    size: float = DEFAULT_SIZE
    locked: bool = True
    start_at_login: bool = False
    monitor: str | None = None


def _finite(value: float) -> bool:
    return math.isfinite(value)


def sanitize(settings: AppSettings) -> AppSettings:
    if settings.left is not None and not _finite(settings.left):
        settings.left = None
    if settings.top is not None and not _finite(settings.top):
        settings.top = None

    if not _finite(settings.size) or settings.size < MIN_SIZE or settings.size > MAX_SIZE:
        settings.size = DEFAULT_SIZE

    # The Windows app shipped a 260px face, then halved it.
    if abs(settings.size - LEGACY_DEFAULT_SIZE) < 0.5:
        settings.size = DEFAULT_SIZE

    if settings.monitor is not None and not str(settings.monitor).strip():
        settings.monitor = None
    return settings


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)
    if not _finite(number):
        return None
    return number


def settings_from_json(data: dict) -> AppSettings:
    start = data.get("startAtLogin", data.get("startWithWindows", False))
    monitor = data.get("monitor")
    return AppSettings(
        left=_optional_float(data.get("left")),
        top=_optional_float(data.get("top")),
        size=float(data.get("size", DEFAULT_SIZE)),
        locked=bool(data.get("locked", True)),
        start_at_login=bool(start),
        monitor=str(monitor) if isinstance(monitor, str) else None,
    )


def settings_to_json(settings: AppSettings) -> dict:
    payload: dict = {
        "left": settings.left,
        "top": settings.top,
        "size": settings.size,
        "locked": settings.locked,
        "startAtLogin": settings.start_at_login,
        "monitor": settings.monitor,
    }
    return payload


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
            base = Path(config_home) if config_home else Path.home() / ".config"
            path = base / "widgie-clock" / "settings.json"
        self.path = path

    def load(self) -> AppSettings:
        try:
            if not self.path.exists():
                return AppSettings()
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return AppSettings()
            return sanitize(settings_from_json(data))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return AppSettings()

    def save(self, settings: AppSettings) -> None:
        sanitize(settings)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(settings_to_json(settings), indent=2) + "\n"
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(self.path)
