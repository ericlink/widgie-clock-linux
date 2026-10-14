"""Tray menu contents. Labels match the Windows app, with login in place of Windows startup."""

from __future__ import annotations

LOCK_ID = 1
STARTUP_ID = 2
SEPARATOR_ID = 3
EXIT_ID = 4


def lock_label(locked: bool) -> str:
    return "Unlock to move" if locked else "Lock (click-through)"


def menu_click(visible: bool, dismissed_by_click: bool) -> str:
    """Click opens the menu. The next click closes it.

    A popover hides itself before the owner's click handler runs, so that
    second click shows up with the menu already gone. Leave it closed.
    """
    if visible:
        return "close"
    if dismissed_by_click:
        return "ignore"
    return "open"


def menu_tree(locked: bool, start_at_login: bool) -> dict:
    return {
        "id": 0,
        "props": {"children-display": "submenu"},
        "children": [
            {
                "id": LOCK_ID,
                "props": {
                    "type": "standard",
                    "label": lock_label(locked),
                    "enabled": True,
                    "visible": True,
                },
            },
            {
                "id": STARTUP_ID,
                "props": {
                    "type": "standard",
                    "label": "Start at login",
                    "enabled": True,
                    "visible": True,
                    "toggle-type": "checkmark",
                    "toggle-state": 1 if start_at_login else 0,
                },
            },
            {
                "id": SEPARATOR_ID,
                "props": {"type": "separator", "enabled": True, "visible": True},
            },
            {
                "id": EXIT_ID,
                "props": {
                    "type": "standard",
                    "label": "Exit",
                    "enabled": True,
                    "visible": True,
                },
            },
        ],
    }


def find_item(node: dict, item_id: int) -> dict | None:
    if node["id"] == item_id:
        return node
    for child in node.get("children", []):
        found = find_item(child, item_id)
        if found is not None:
            return found
    return None
