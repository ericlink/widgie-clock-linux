"""Application entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from widgie_clock.layer_preload import ensure_layer_shell_preload

ensure_layer_shell_preload()

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gio, Gtk, Gtk4LayerShell

from widgie_clock.autostart import sync
from widgie_clock.settings import SettingsStore
from widgie_clock.tray import try_tray
from widgie_clock.window import ClockOverlay


def launch_command() -> str:
    launcher = Path(__file__).resolve().parent.parent / "widgie-clock"
    if launcher.is_file():
        return str(launcher)
    return f"{sys.executable} -m widgie_clock"


class WidgieApplication(Gtk.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id="com.ericlink.WidgieClock",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self._overlay: ClockOverlay | None = None

    def do_activate(self) -> None:
        if self._overlay is not None:
            return
        if not Gtk4LayerShell.is_supported():
            sys.stderr.write(
                "Widgie Clock needs a Wayland compositor with wlr-layer-shell.\n"
            )
            self.quit()
            return

        store = SettingsStore()
        settings = store.load()
        command = launch_command()
        sync(settings.start_at_login, command)
        try:
            self._overlay = ClockOverlay(self, settings, store, command)
        except Exception as exc:
            sys.stderr.write(f"Widgie Clock: {exc}\n")
            self.quit()
            return

        self._overlay.tray = try_tray(
            on_lock=self._overlay.set_locked,
            on_startup=self._overlay.set_start_at_login,
            on_exit=self.quit,
            locked=settings.locked,
            start_at_login=settings.start_at_login,
        )
        if self._overlay.tray is None and settings.locked:
            # Without a tray there is no way to reach a click-through face.
            self._overlay.set_locked(False)


def main() -> int:
    app = WidgieApplication()
    return app.run(sys.argv)
