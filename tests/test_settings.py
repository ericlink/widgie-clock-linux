import json
import unittest
from pathlib import Path

from widgie_clock.placement import clamp_origin, default_origin
from widgie_clock.settings import (
    DEFAULT_SIZE,
    AppSettings,
    SettingsStore,
    sanitize,
    settings_from_json,
)


class SanitizeTests(unittest.TestCase):
    def test_legacy_size_migrates_to_half(self) -> None:
        settings = sanitize(AppSettings(size=260))
        self.assertEqual(settings.size, DEFAULT_SIZE)

    def test_out_of_range_size_resets(self) -> None:
        self.assertEqual(sanitize(AppSettings(size=10)).size, DEFAULT_SIZE)
        self.assertEqual(sanitize(AppSettings(size=1000)).size, DEFAULT_SIZE)
        self.assertEqual(sanitize(AppSettings(size=float("nan"))).size, DEFAULT_SIZE)

    def test_non_finite_position_is_cleared(self) -> None:
        settings = sanitize(AppSettings(left=float("inf"), top=float("nan"), size=160))
        self.assertIsNone(settings.left)
        self.assertIsNone(settings.top)
        self.assertEqual(settings.size, 160)

    def test_windows_startup_key_is_accepted(self) -> None:
        settings = settings_from_json({"startWithWindows": True, "locked": False})
        self.assertTrue(settings.start_at_login)
        self.assertFalse(settings.locked)


class StoreTests(unittest.TestCase):
    def test_round_trip(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            store = SettingsStore(path)
            original = store.load()
            self.assertTrue(original.locked)
            self.assertEqual(original.size, DEFAULT_SIZE)

            original.left = 12
            original.top = 34
            original.monitor = "HDMI-A-1"
            original.start_at_login = True
            store.save(original)

            loaded = SettingsStore(path).load()
            self.assertEqual(loaded.left, 12)
            self.assertEqual(loaded.top, 34)
            self.assertEqual(loaded.monitor, "HDMI-A-1")
            self.assertTrue(loaded.start_at_login)
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("startAtLogin", payload)
            self.assertNotIn("startWithWindows", payload)

    def test_corrupt_file_falls_back(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            path.write_text("{", encoding="utf-8")
            settings = SettingsStore(path).load()
            self.assertEqual(settings.size, DEFAULT_SIZE)
            self.assertTrue(settings.locked)


class PlacementTests(unittest.TestCase):
    def test_default_is_a_24px_inset(self) -> None:
        left, top = default_origin(3840, 2160, 130, (0, 35, 0, 0))
        self.assertEqual(left, 3840 - 130 - 24)
        self.assertEqual(top, 24)

    def test_clamp_keeps_a_sliver_on_screen(self) -> None:
        left, top = clamp_origin(10000, -500, 130, 800, 600)
        self.assertEqual(left, 800 - 24)
        self.assertEqual(top, -(130 - 24))


if __name__ == "__main__":
    unittest.main()
