import json
import os
import stat
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from pitwall import settings


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "settings.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_every_feature_is_on_without_a_file(self):
        self.assertEqual(settings.current(self.path), settings.DEFAULTS)
        self.assertTrue(all(settings.DEFAULTS.values()))

    def test_a_corrupt_file_gives_the_defaults_and_stays_as_it_is(self):
        self.path.write_text("{not json")
        with redirect_stdout(StringIO()) as out:
            self.assertEqual(settings.current(self.path), settings.DEFAULTS)
        self.assertIn("not valid JSON", out.getvalue())
        self.assertEqual(self.path.read_text(), "{not json")

    def test_a_file_that_is_not_an_object_gives_the_defaults(self):
        self.path.write_text("[1, 2]")
        self.assertEqual(settings.current(self.path), settings.DEFAULTS)

    def test_unknown_keys_and_odd_values_in_the_file_are_ignored(self):
        self.path.write_text(json.dumps({"ports": False, "map": "no", "someday": False}))
        values = settings.current(self.path)
        self.assertFalse(values["ports"])
        self.assertTrue(values["map"])
        self.assertNotIn("someday", values)

    def test_update_saves_and_merges(self):
        settings.update({"ports": False}, self.path)
        settings.update({"map": False}, self.path)
        values = settings.current(self.path)
        self.assertFalse(values["ports"])
        self.assertFalse(values["map"])
        self.assertTrue(values["undo"])
        self.assertEqual(stat.S_IMODE(os.stat(self.path).st_mode), 0o600)

    def test_update_refuses_bad_input_and_writes_nothing(self):
        for bad in ({"someday": False}, {"ports": "off"}, {"ports": 0}):
            with self.assertRaises(ValueError):
                settings.update(bad, self.path)
        self.assertFalse(self.path.exists())

    def test_a_hand_edit_is_read_again(self):
        self.assertTrue(settings.current(self.path)["undo"])
        self.path.write_text(json.dumps({"undo": False}))
        self.assertFalse(settings.current(self.path)["undo"])
        self.path.write_text(json.dumps({"undo": True}))
        self.assertTrue(settings.current(self.path)["undo"])

    def test_the_update_check_variable_forces_the_check_off(self):
        rows = {r["key"]: r for r in settings.describe({"PITWALL_UPDATE_CHECK": "0"}, self.path)}
        self.assertFalse(rows["update_check"]["on"])
        self.assertEqual(rows["update_check"]["locked"], "PITWALL_UPDATE_CHECK=0")
        self.assertIsNone(rows["ports"]["locked"])
        self.assertFalse(settings.on("update_check", {"PITWALL_UPDATE_CHECK": "0"}, self.path))
        self.assertTrue(settings.on("update_check", {}, self.path))

    def test_describe_lists_every_feature_in_order(self):
        self.assertEqual([r["key"] for r in settings.describe({}, self.path)], [f[0] for f in settings.FEATURES])


if __name__ == "__main__":
    unittest.main()
