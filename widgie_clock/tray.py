"""StatusNotifierItem and a DBus menu for the Omarchy tray."""

from __future__ import annotations

import struct
import sys
from collections.abc import Callable
from datetime import datetime

import cairo

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib

from widgie_clock.clock import draw_clock, hand_angles
from widgie_clock.menu import EXIT_ID, LOCK_ID, STARTUP_ID, find_item, menu_tree

SNI_IFACE = "org.kde.StatusNotifierItem"
MENU_IFACE = "com.canonical.dbusmenu"
PROPS_IFACE = "org.freedesktop.DBus.Properties"
WATCHER_BUS = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM_PATH = "/StatusNotifierItem"
MENU_PATH = "/Menu"

_SNI_XML = """
<node>
  <interface name="org.kde.StatusNotifierItem">
    <property name="Category" type="s" access="read"/>
    <property name="Id" type="s" access="read"/>
    <property name="Title" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="WindowId" type="i" access="read"/>
    <property name="IconThemePath" type="s" access="read"/>
    <property name="IconName" type="s" access="read"/>
    <property name="IconPixmap" type="a(iiay)" access="read"/>
    <property name="OverlayIconName" type="s" access="read"/>
    <property name="OverlayIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionIconName" type="s" access="read"/>
    <property name="AttentionIconPixmap" type="a(iiay)" access="read"/>
    <property name="AttentionMovieName" type="s" access="read"/>
    <property name="ItemIsMenu" type="b" access="read"/>
    <property name="Menu" type="o" access="read"/>
    <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
    <method name="ContextMenu">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Activate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="SecondaryActivate">
      <arg name="x" type="i" direction="in"/>
      <arg name="y" type="i" direction="in"/>
    </method>
    <method name="Scroll">
      <arg name="delta" type="i" direction="in"/>
      <arg name="orientation" type="s" direction="in"/>
    </method>
    <method name="ProvideXdgActivationToken">
      <arg name="token" type="s" direction="in"/>
    </method>
    <signal name="NewTitle"/>
    <signal name="NewIcon"/>
    <signal name="NewAttentionIcon"/>
    <signal name="NewOverlayIcon"/>
    <signal name="NewMenu"/>
    <signal name="NewToolTip"/>
    <signal name="NewStatus">
      <arg name="status" type="s"/>
    </signal>
  </interface>
</node>
"""

_MENU_XML = """
<node>
  <interface name="com.canonical.dbusmenu">
    <property name="Version" type="u" access="read"/>
    <property name="TextDirection" type="s" access="read"/>
    <property name="Status" type="s" access="read"/>
    <property name="IconThemePath" type="as" access="read"/>
    <method name="GetLayout">
      <arg name="parentId" type="i" direction="in"/>
      <arg name="recursionDepth" type="i" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="revision" type="u" direction="out"/>
      <arg name="layout" type="(ia{sv}av)" direction="out"/>
    </method>
    <method name="GetGroupProperties">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="propertyNames" type="as" direction="in"/>
      <arg name="properties" type="a(ia{sv})" direction="out"/>
    </method>
    <method name="GetProperty">
      <arg name="id" type="i" direction="in"/>
      <arg name="name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="Event">
      <arg name="id" type="i" direction="in"/>
      <arg name="eventId" type="s" direction="in"/>
      <arg name="data" type="v" direction="in"/>
      <arg name="timestamp" type="u" direction="in"/>
    </method>
    <method name="EventGroup">
      <arg name="events" type="a(isvu)" direction="in"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <method name="AboutToShow">
      <arg name="id" type="i" direction="in"/>
      <arg name="needUpdate" type="b" direction="out"/>
    </method>
    <method name="AboutToShowGroup">
      <arg name="ids" type="ai" direction="in"/>
      <arg name="updatesNeeded" type="ai" direction="out"/>
      <arg name="idErrors" type="ai" direction="out"/>
    </method>
    <signal name="ItemsPropertiesUpdated">
      <arg name="updatedProps" type="a(ia{sv})"/>
      <arg name="removedProps" type="a(ias)"/>
    </signal>
    <signal name="LayoutUpdated">
      <arg name="revision" type="u"/>
      <arg name="parent" type="i"/>
    </signal>
    <signal name="ItemActivationRequested">
      <arg name="id" type="i"/>
      <arg name="timestamp" type="u"/>
    </signal>
  </interface>
</node>
"""

_PROPS_XML = """
<node>
  <interface name="org.freedesktop.DBus.Properties">
    <method name="Get">
      <arg name="interface_name" type="s" direction="in"/>
      <arg name="property_name" type="s" direction="in"/>
      <arg name="value" type="v" direction="out"/>
    </method>
    <method name="GetAll">
      <arg name="interface_name" type="s" direction="in"/>
      <arg name="properties" type="a{sv}" direction="out"/>
    </method>
    <method name="Set">
      <arg name="interface_name" type="s" direction="in"/>
      <arg name="property_name" type="s" direction="in"/>
      <arg name="value" type="v" direction="in"/>
    </method>
    <signal name="PropertiesChanged">
      <arg name="interface_name" type="s"/>
      <arg name="changed_properties" type="a{sv}"/>
      <arg name="invalidated_properties" type="as"/>
    </signal>
  </interface>
</node>
"""


def _boxed(value):
    if isinstance(value, str):
        return GLib.Variant("s", value)
    if isinstance(value, bool):
        return GLib.Variant("b", value)
    if isinstance(value, int):
        return GLib.Variant("i", value)
    raise TypeError(f"unsupported menu property {value!r}")


def layout_variant(node: dict, depth: int, names: list[str]) -> GLib.Variant:
    props = {}
    for key, value in node["props"].items():
        if names and key not in names:
            continue
        props[key] = _boxed(value)

    children = []
    if depth != 0:
        next_depth = -1 if depth < 0 else depth - 1
        for child in node.get("children", []):
            children.append(layout_variant(child, next_depth, names))
    return GLib.Variant("(ia{sv}av)", (int(node["id"]), props, children))


def _icon_bytes(size: int) -> bytes:
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    moment = datetime(2026, 1, 1, 10, 10, 30)
    draw_clock(cairo.Context(surface), size, size, hand_angles(moment))
    surface.flush()
    words = struct.unpack_from(f"={size * size}I", surface.get_data())
    raw = bytearray(size * size * 4)
    for index, word in enumerate(words):
        alpha = (word >> 24) & 255
        red = (word >> 16) & 255
        green = (word >> 8) & 255
        blue = word & 255
        if 0 < alpha < 255:
            red = min(255, (red * 255 + alpha // 2) // alpha)
            green = min(255, (green * 255 + alpha // 2) // alpha)
            blue = min(255, (blue * 255 + alpha // 2) // alpha)
        offset = index * 4
        raw[offset] = alpha
        raw[offset + 1] = red
        raw[offset + 2] = green
        raw[offset + 3] = blue
    return bytes(raw)


def _interface(xml: str) -> Gio.DBusInterfaceInfo:
    node = Gio.DBusNodeInfo.new_for_xml(xml)
    return node.interfaces[0]


def _register(connection, path: str, interface: Gio.DBusInterfaceInfo, handler) -> int:
    return connection.register_object(path, interface, handler, None, None)


class Tray:
    def __init__(
        self,
        on_lock: Callable[[bool], None],
        on_startup: Callable[[bool], None],
        on_exit: Callable[[], None],
        locked: bool,
        start_at_login: bool,
    ) -> None:
        self._on_lock = on_lock
        self._on_startup = on_startup
        self._on_exit = on_exit
        self.locked = locked
        self.start_at_login = start_at_login
        self._revision = 1
        self._tree = menu_tree(locked, start_at_login)

        icon = _icon_bytes(48)
        icon_small = _icon_bytes(22)
        empty: list = []
        self._item_props = {
            "Category": GLib.Variant("s", "ApplicationStatus"),
            "Id": GLib.Variant("s", "widgie-clock"),
            "Title": GLib.Variant("s", "Widgie Clock"),
            "Status": GLib.Variant("s", "Active"),
            "WindowId": GLib.Variant("i", 0),
            "IconThemePath": GLib.Variant("s", ""),
            "IconName": GLib.Variant("s", "preferences-system-time"),
            "IconPixmap": GLib.Variant("a(iiay)", [(48, 48, icon), (22, 22, icon_small)]),
            "OverlayIconName": GLib.Variant("s", ""),
            "OverlayIconPixmap": GLib.Variant("a(iiay)", empty),
            "AttentionIconName": GLib.Variant("s", ""),
            "AttentionIconPixmap": GLib.Variant("a(iiay)", empty),
            "AttentionMovieName": GLib.Variant("s", ""),
            "ItemIsMenu": GLib.Variant("b", True),
            "Menu": GLib.Variant("o", MENU_PATH),
            "ToolTip": GLib.Variant(
                "(sa(iiay)ss)",
                ("preferences-system-time", empty, "Widgie Clock", "Floating analog clock"),
            ),
        }
        self._menu_props = {
            "Version": GLib.Variant("u", 3),
            "TextDirection": GLib.Variant("s", "ltr"),
            "Status": GLib.Variant("s", "normal"),
            "IconThemePath": GLib.Variant("as", []),
        }

        self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self._register_source = 0
        self._regs = [
            _register(self._connection, ITEM_PATH, _interface(_SNI_XML), self._on_item_call),
            _register(self._connection, ITEM_PATH, _interface(_PROPS_XML), self._on_item_props),
            _register(self._connection, MENU_PATH, _interface(_MENU_XML), self._on_menu_call),
            _register(self._connection, MENU_PATH, _interface(_PROPS_XML), self._on_menu_props),
        ]
        # The bar owns the watcher. Restarting the shell drops every item that
        # does not register again, which leaves an empty tray slot.
        self._subs = (
            self._connection.signal_subscribe(
                WATCHER_BUS,
                WATCHER_BUS,
                "StatusNotifierHostRegistered",
                WATCHER_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                self._schedule_register,
            ),
            self._connection.signal_subscribe(
                "org.freedesktop.DBus",
                "org.freedesktop.DBus",
                "NameOwnerChanged",
                "/org/freedesktop/DBus",
                WATCHER_BUS,
                Gio.DBusSignalFlags.NONE,
                self._on_watcher_owner,
            ),
        )
        self._register_sync()
        self._connection.emit_signal(None, ITEM_PATH, SNI_IFACE, "NewIcon", None)
        self._connection.emit_signal(None, ITEM_PATH, SNI_IFACE, "NewTitle", None)

    def _register_sync(self) -> None:
        try:
            self._connection.call_sync(
                WATCHER_BUS,
                WATCHER_PATH,
                WATCHER_BUS,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (ITEM_PATH,)),
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
            )
        except GLib.Error as exc:
            # The bar may not be up yet. NameOwnerChanged registers us when it is.
            print(f"widgie-clock: tray register failed: {exc}", file=sys.stderr)

    def _on_watcher_owner(self, _connection, _sender, _path, _interface, _signal, params) -> None:
        _name, _old, new = params.unpack()
        if new:
            self._schedule_register()

    def _schedule_register(self, *_args) -> None:
        if self._register_source:
            return
        self._register_source = GLib.timeout_add(300, self._register_soon)

    def _register_soon(self) -> bool:
        self._register_source = 0
        try:
            self._connection.call(
                WATCHER_BUS,
                WATCHER_PATH,
                WATCHER_BUS,
                "RegisterStatusNotifierItem",
                GLib.Variant("(s)", (ITEM_PATH,)),
                None,
                Gio.DBusCallFlags.NONE,
                3000,
                None,
                self._on_register_done,
                None,
            )
        except GLib.Error as exc:
            print(f"widgie-clock: tray register failed: {exc}", file=sys.stderr)
        return False

    def _on_register_done(self, _source, result, *_data) -> None:
        try:
            self._connection.call_finish(result)
        except GLib.Error as exc:
            print(f"widgie-clock: tray register failed: {exc}", file=sys.stderr)

    def update(self, locked: bool, start_at_login: bool) -> None:
        self.locked = locked
        self.start_at_login = start_at_login
        self._tree = menu_tree(locked, start_at_login)
        self._revision += 1
        self._connection.emit_signal(
            None,
            MENU_PATH,
            MENU_IFACE,
            "LayoutUpdated",
            GLib.Variant("(ui)", (self._revision, 0)),
        )

    def _clicked(self, item_id: int) -> None:
        if item_id == LOCK_ID:
            self._on_lock(not self.locked)
        elif item_id == STARTUP_ID:
            self._on_startup(not self.start_at_login)
        elif item_id == EXIT_ID:
            self._on_exit()

    def _on_item_call(self, _connection, _sender, _path, _interface, method, params, invocation):
        del params
        if method in {"ContextMenu", "Activate", "SecondaryActivate", "Scroll", "ProvideXdgActivationToken"}:
            invocation.return_value(None)
            return
        invocation.return_error_literal(
            "org.freedesktop.DBus.Error.UnknownMethod",
            method,
        )

    def _on_menu_call(self, _connection, _sender, _path, _interface, method, params, invocation):
        try:
            invocation.return_value(self._menu_result(method, params))
        except Exception as exc:
            invocation.return_error_literal("org.freedesktop.DBus.Error.Failed", str(exc))

    def _menu_result(self, method: str, params: GLib.Variant):
        if method == "GetLayout":
            parent_id, depth, names = params.unpack()
            node = find_item(self._tree, int(parent_id)) or {
                "id": int(parent_id),
                "props": {},
                "children": [],
            }
            layout = layout_variant(node, int(depth), [str(name) for name in names])
            return GLib.Variant.new_tuple(GLib.Variant("u", self._revision), layout)
        if method == "AboutToShow":
            return GLib.Variant("(b)", (False,))
        if method == "AboutToShowGroup":
            return GLib.Variant("(aiai)", ([], []))
        if method == "Event":
            item_id, event_id, _data, _timestamp = params.unpack()
            if event_id == "clicked":
                self._clicked(int(item_id))
            return None
        if method == "EventGroup":
            errors = []
            for item_id, event_id, data, timestamp in params.unpack()[0]:
                try:
                    if event_id == "clicked":
                        self._clicked(int(item_id))
                except Exception:
                    errors.append(int(item_id))
                del data, timestamp
            return GLib.Variant("(ai)", (errors,))
        if method == "GetGroupProperties":
            ids, names = params.unpack()
            wanted = [str(name) for name in names]
            rows = []
            for item_id in ids:
                node = find_item(self._tree, int(item_id))
                props = {}
                if node is not None:
                    for key, value in node["props"].items():
                        if wanted and key not in wanted:
                            continue
                        props[key] = _boxed(value)
                rows.append((int(item_id), props))
            return GLib.Variant("(a(ia{sv}))", (rows,))
        if method == "GetProperty":
            item_id, name = params.unpack()
            node = find_item(self._tree, int(item_id))
            value = node["props"].get(str(name)) if node else None
            boxed = _boxed(value) if value is not None else GLib.Variant("s", "")
            return GLib.Variant("(v)", (boxed,))
        raise RuntimeError(method)

    def _on_item_props(self, _connection, _sender, _path, _interface, method, params, invocation):
        self._props_call(self._item_props, method, params, invocation)

    def _on_menu_props(self, _connection, _sender, _path, _interface, method, params, invocation):
        self._props_call(self._menu_props, method, params, invocation)

    def _props_call(self, props: dict, method: str, params: GLib.Variant, invocation) -> None:
        try:
            if method == "GetAll":
                interface_name = params.unpack()[0]
                payload = props if interface_name in (SNI_IFACE, MENU_IFACE, "") else {}
                invocation.return_value(GLib.Variant("(a{sv})", (payload,)))
                return
            if method == "Get":
                _interface_name, name = params.unpack()
                invocation.return_value(GLib.Variant("(v)", (props[str(name)],)))
                return
            if method == "Set":
                invocation.return_value(None)
                return
        except Exception as exc:
            invocation.return_error_literal("org.freedesktop.DBus.Error.Failed", str(exc))
            return
        invocation.return_error_literal("org.freedesktop.DBus.Error.UnknownMethod", method)


def try_tray(**kwargs) -> Tray | None:
    try:
        return Tray(**kwargs)
    except Exception as exc:
        sys.stderr.write(
            "Widgie Clock: tray icon unavailable "
            f"({exc}). Right-click the face to use the menu.\n"
        )
        return None
