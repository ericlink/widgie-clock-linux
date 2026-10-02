"""Login autostart via the XDG autostart desktop file systemd already honors."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

MARKER = "X-Widgie-Clock=true"
DESKTOP_NAME = "widgie-clock.desktop"


def autostart_path() -> Path:
    config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(config_home) if config_home else Path.home() / ".config"
    return base / "autostart" / DESKTOP_NAME


def desktop_text(command: str) -> str:
    exec_line = command if " " not in command else "'" + command.replace("'", "'\\''") + "'"
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Version=1.0\n"
        "Name=Widgie Clock\n"
        "Comment=Floating analog clock\n"
        f"Exec={exec_line}\n"
        "Icon=preferences-system-time\n"
        "Terminal=false\n"
        "Categories=Utility;\n"
        "StartupNotify=false\n"
        "X-GNOME-Autostart-enabled=true\n"
        f"{MARKER}\n"
    )


def is_enabled(path: Path | None = None) -> bool:
    path = path or autostart_path()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    return MARKER in text and "X-GNOME-Autostart-enabled=false" not in text


def _reload_user_manager() -> None:
    try:
        subprocess.run(
            ["systemctl", "--user", "daemon-reload"],
            check=False,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (OSError, subprocess.SubprocessError):
        return


def set_enabled(
    enabled: bool,
    command: str,
    path: Path | None = None,
    *,
    reload: bool = True,
) -> None:
    path = path or autostart_path()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desktop_text(command), encoding="utf-8")
    else:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        if MARKER in text:
            path.unlink(missing_ok=True)
        elif not path.exists():
            return
        else:
            return
    if reload:
        _reload_user_manager()


def sync(enabled: bool, command: str, path: Path | None = None, *, reload: bool = True) -> None:
    """Make the desktop file match settings. Settings win, as they do on Windows."""

    path = path or autostart_path()
    if enabled:
        desired = desktop_text(command)
        try:
            current = path.read_text(encoding="utf-8")
        except OSError:
            current = None
        if current != desired:
            set_enabled(True, command, path, reload=reload)
        return

    if is_enabled(path):
        set_enabled(False, command, path, reload=reload)
