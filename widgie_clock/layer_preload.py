"""Load gtk4-layer-shell before libwayland.

Python loads libwayland first, and gtk4-layer-shell's Wayland shim then never
installs. Preloading the library fixes that. See gtk4-layer-shell's linking.md.
"""

from __future__ import annotations

import os
import sys

_LIBRARY_CANDIDATES = (
    "/usr/lib/libgtk4-layer-shell.so",
    "/usr/lib/libgtk4-layer-shell.so.0",
)


def ensure_layer_shell_preload() -> None:
    preload = os.environ.get("LD_PRELOAD", "")
    if "libgtk4-layer-shell" in preload:
        return
    library = next((path for path in _LIBRARY_CANDIDATES if os.path.exists(path)), None)
    if library is None:
        return
    env = os.environ.copy()
    env["LD_PRELOAD"] = library if not preload else f"{library} {preload}"
    os.execvpe(sys.executable, [sys.executable, *sys.argv], env)
