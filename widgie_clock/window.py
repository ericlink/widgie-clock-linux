"""Overlay window: layer-shell, click-through, and drag-to-move."""

from __future__ import annotations

import cairo

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gtk4LayerShell", "1.0")
from gi.repository import Gdk, GLib, Gtk, Gtk4LayerShell

from widgie_clock.autostart import set_enabled
from widgie_clock.clock import draw_clock, hand_angles
from widgie_clock.menu import lock_label
from widgie_clock.outputs import choose_output, list_outputs
from widgie_clock.placement import clamp_origin, default_origin
from widgie_clock.settings import AppSettings, SettingsStore

from datetime import datetime


_CSS = """
window.widgie-clock,
drawingarea.widgie-face {
  background-color: transparent;
}
"""


class ClockOverlay:
    def __init__(
        self,
        application: Gtk.Application,
        settings: AppSettings,
        store: SettingsStore,
        command: str,
    ) -> None:
        self.settings = settings
        self.store = store
        self.command = command
        self.tray = None
        self._updating_menu = False
        self._drag_origin = (0, 0)

        output = choose_output(list_outputs(), settings.monitor)
        if output is None:
            raise RuntimeError("no monitor is available")
        self.output = output
        self.size = int(round(settings.size))

        if settings.left is None or settings.top is None:
            origin = default_origin(output.width, output.height, self.size, output.reserved)
        else:
            origin = (settings.left, settings.top)
        self.left, self.top = clamp_origin(
            origin[0], origin[1], self.size, output.width, output.height
        )
        self._capture()
        self.store.save(self.settings)

        self.window = Gtk.Window(title="Widgie Clock", application=application)
        self.window.add_css_class("widgie-clock")
        self.window.set_decorated(False)
        self.window.set_resizable(False)
        self.window.set_focusable(False)
        self.window.set_default_size(self.size, self.size)
        self.window.set_size_request(self.size, self.size)
        self._install_css()
        self._init_layer()

        self.face = Gtk.DrawingArea()
        self.face.add_css_class("widgie-face")
        self.face.set_content_width(self.size)
        self.face.set_content_height(self.size)
        self.face.set_draw_func(self._draw)
        self.face.add_tick_callback(self._on_tick)
        self.window.set_child(self.face)

        self._drag = Gtk.GestureDrag()
        self._drag.set_button(1)
        self._drag.connect("drag-begin", self._on_drag_begin)
        self._drag.connect("drag-update", self._on_drag_update)
        self._drag.connect("drag-end", self._on_drag_end)
        self.face.add_controller(self._drag)

        right_click = Gtk.GestureClick()
        right_click.set_button(3)
        right_click.connect("pressed", self._on_right_click)
        self.face.add_controller(right_click)

        self.popover = Gtk.Popover()
        self.popover.set_parent(self.face)
        self.popover.set_has_arrow(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        self._lock_button = Gtk.Button()
        self._lock_button.connect("clicked", self._on_lock_clicked)
        self._startup_button = Gtk.CheckButton(label="Start at login")
        self._startup_button.connect("toggled", self._on_startup_toggled)
        exit_button = Gtk.Button(label="Exit")
        exit_button.connect("clicked", lambda *_: application.quit())
        box.append(self._lock_button)
        box.append(self._startup_button)
        box.append(exit_button)
        self.popover.set_child(box)
        self._refresh_menu()

        self._apply_cursor()
        self.window.connect("map", lambda *_: GLib.idle_add(self._apply_input))
        self.window.present()

    def set_locked(self, locked: bool) -> None:
        self.settings.locked = bool(locked)
        self._apply_cursor()
        self._apply_input()
        self._refresh_menu()
        self._notify_tray()
        self._capture()
        self.store.save(self.settings)
        if self.settings.locked:
            self.popover.popdown()

    def set_start_at_login(self, enabled: bool) -> None:
        self.settings.start_at_login = bool(enabled)
        set_enabled(self.settings.start_at_login, self.command)
        self._refresh_menu()
        self._notify_tray()
        self.store.save(self.settings)

    def _notify_tray(self) -> None:
        if self.tray is not None:
            self.tray.update(self.settings.locked, self.settings.start_at_login)

    def _capture(self) -> None:
        self.settings.left = float(self.left)
        self.settings.top = float(self.top)
        self.settings.size = float(self.size)
        self.settings.monitor = self.output.connector

    def _apply_margins(self) -> None:
        Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.LEFT, int(self.left))
        Gtk4LayerShell.set_margin(self.window, Gtk4LayerShell.Edge.TOP, int(self.top))

    def _init_layer(self) -> None:
        if not Gtk4LayerShell.is_supported():
            raise RuntimeError("this compositor does not support wlr-layer-shell")
        Gtk4LayerShell.init_for_window(self.window)
        Gtk4LayerShell.set_namespace(self.window, "widgie-clock")
        Gtk4LayerShell.set_layer(self.window, Gtk4LayerShell.Layer.OVERLAY)
        Gtk4LayerShell.set_keyboard_mode(self.window, Gtk4LayerShell.KeyboardMode.NONE)
        Gtk4LayerShell.set_exclusive_zone(self.window, 0)
        Gtk4LayerShell.set_monitor(self.window, self.output.monitor)
        for edge in (
            Gtk4LayerShell.Edge.LEFT,
            Gtk4LayerShell.Edge.RIGHT,
            Gtk4LayerShell.Edge.TOP,
            Gtk4LayerShell.Edge.BOTTOM,
        ):
            Gtk4LayerShell.set_anchor(self.window, edge, False)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.LEFT, True)
        Gtk4LayerShell.set_anchor(self.window, Gtk4LayerShell.Edge.TOP, True)
        self._apply_margins()

    def _install_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_string(_CSS)
        display = self.window.get_display() or Gdk.Display.get_default()
        Gtk.StyleContext.add_provider_for_display(
            display,
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _apply_cursor(self) -> None:
        name = "default" if self.settings.locked else "all-scroll"
        self.window.set_cursor(Gdk.Cursor.new_from_name(name, None))

    def _apply_input(self) -> bool:
        surface = self.window.get_surface()
        if surface is None:
            return False
        if self.settings.locked:
            surface.set_input_region(cairo.Region())
        else:
            surface.set_input_region(None)
        return False

    def _draw(self, _area, cr, width: int, height: int) -> None:
        draw_clock(cr, width, height, hand_angles(datetime.now()))

    def _on_tick(self, widget, _frame_clock, _data=None) -> bool:
        widget.queue_draw()
        if self.settings.locked:
            self._apply_input()
        return GLib.SOURCE_CONTINUE

    def _on_drag_begin(self, _gesture, _x, _y) -> None:
        self._drag_origin = (self.left, self.top)

    def _on_drag_update(self, _gesture, dx: float, dy: float) -> None:
        if self.settings.locked:
            return
        self.left, self.top = clamp_origin(
            self._drag_origin[0] + dx,
            self._drag_origin[1] + dy,
            self.size,
            self.output.width,
            self.output.height,
        )
        self._apply_margins()

    def _on_drag_end(self, gesture, dx: float, dy: float) -> None:
        self._on_drag_update(gesture, dx, dy)
        if self.settings.locked:
            return
        self._capture()
        self.store.save(self.settings)

    def _on_right_click(self, _gesture, _n_press, x: float, y: float) -> None:
        if self.settings.locked:
            return
        rect = Gdk.Rectangle()
        rect.x = int(x)
        rect.y = int(y)
        rect.width = 1
        rect.height = 1
        self.popover.set_pointing_to(rect)
        self.popover.popup()

    def _on_lock_clicked(self, _button) -> None:
        self.popover.popdown()
        self.set_locked(not self.settings.locked)

    def _on_startup_toggled(self, button) -> None:
        if self._updating_menu:
            return
        self.popover.popdown()
        self.set_start_at_login(button.get_active())

    def _refresh_menu(self) -> None:
        self._updating_menu = True
        self._lock_button.set_label(lock_label(self.settings.locked))
        self._startup_button.set_active(self.settings.start_at_login)
        self._updating_menu = False
