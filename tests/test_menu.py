import unittest

from widgie_clock.autostart import MARKER, desktop_text, is_enabled, set_enabled, sync
from widgie_clock.menu import EXIT_ID, LOCK_ID, STARTUP_ID, lock_label, menu_tree
from widgie_clock.tray import layout_variant


class MenuTests(unittest.TestCase):
    def test_lock_label_matches_windows(self) -> None:
        self.assertEqual(lock_label(True), "Unlock to move")
        self.assertEqual(lock_label(False), "Lock (click-through)")

    def test_layout_carries_startup_checkmark(self) -> None:
        item_id, _props, children = layout_variant(menu_tree(True, True), -1, []).unpack()
        self.assertEqual(item_id, 0)
        self.assertEqual(len(children), 4)
        by_id = {child[0]: child[1] for child in children}
        self.assertEqual(by_id[LOCK_ID]["label"], "Unlock to move")
        self.assertEqual(by_id[STARTUP_ID]["label"], "Start at login")
        self.assertEqual(by_id[STARTUP_ID]["toggle-state"], 1)
        self.assertEqual(by_id[EXIT_ID]["label"], "Exit")


class AutostartTests(unittest.TestCase):
    def test_sync_writes_and_removes_marked_file(self) -> None:
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "widgie-clock.desktop"
            sync(True, "/home/elink/source/ericlink/widgie-clock-linux/widgie-clock", path, reload=False)
            text = path.read_text(encoding="utf-8")
            self.assertIn(MARKER, text)
            self.assertIn("Exec=/home/elink/source/ericlink/widgie-clock-linux/widgie-clock\n", text)
            self.assertTrue(is_enabled(path))
            self.assertEqual(text, desktop_text("/home/elink/source/ericlink/widgie-clock-linux/widgie-clock"))

            sync(True, "/home/elink/source/ericlink/widgie-clock-linux/widgie-clock", path, reload=False)
            self.assertEqual(path.read_text(encoding="utf-8"), text)

            set_enabled(False, "/bin/widgie-clock", path, reload=False)
            self.assertFalse(path.exists())
            self.assertFalse(is_enabled(path))


if __name__ == "__main__":
    unittest.main()
