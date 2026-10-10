import math
import unittest

from pitwall.codemap import build, category

FILES = ["package.json", "src/app/page.tsx", "src/app/api/cart/route.ts", "src/components/CartSummary.tsx",
         "src/components/Button.tsx", "src/lib/cart.ts", "src/lib/money.ts", "prisma/schema.prisma",
         "migrations/001_init.sql", "tests/cart.test.ts", "public/logo.svg", "docs/deep/a/b/notes.md"]
IMPORTERS = {"src/lib/cart.ts": ["src/components/CartSummary.tsx", "tests/cart.test.ts"],
             "src/components/CartSummary.tsx": ["src/app/page.tsx"]}


def nodes(graph):
    return {n["id"]: n for n in graph["nodes"]}


class CategoryTests(unittest.TestCase):
    def test_deepest_known_folder_wins(self):
        self.assertEqual(category("src/app/api/cart/route.ts"), "backend")
        self.assertEqual(category("src/components/CartSummary.tsx"), "frontend")
        self.assertEqual(category("migrations/001_init.sql"), "database")
        self.assertEqual(category("src/lib/cart.test.ts"), "tests")
        self.assertEqual(category("src/lib/cart.ts"), "code")


class BuildTests(unittest.TestCase):
    def setUp(self):
        touched = {"/r/src/lib/cart.ts": "edit", "/r/src/app/page.tsx": "read", "/elsewhere/x.ts": "read"}
        self.g = build("/r", FILES, touched, "/r/src/lib/cart.ts", IMPORTERS, changed=["migrations/001_init.sql"])
        self.n = nodes(self.g)

    def test_only_the_work_is_shown(self):
        self.assertEqual(self.n["src/lib/cart.ts"]["touch"], "edit")
        self.assertEqual(self.n["src/app/page.tsx"]["touch"], "read")
        self.assertTrue(self.n["src/lib/cart.ts"]["current"])
        for quiet in ("docs", "public", "prisma", "src/lib/money.ts", "src/components/Button.tsx"):
            self.assertNotIn(quiet, self.n)

    def test_folders_appear_only_on_the_path_to_a_file(self):
        self.assertIn("src/lib", self.n)
        self.assertEqual(self.n["src"]["kind"], "folder")

    def test_a_file_changed_outside_the_hooks_counts_as_edited(self):
        self.assertEqual(self.n["migrations/001_init.sql"]["touch"], "edit")
        self.assertEqual(self.g["stats"]["edited"], 2)

    def test_files_outside_the_repo_are_left_out(self):
        self.assertFalse(any("elsewhere" in i for i in self.n))

    def test_blast_radius(self):
        self.assertTrue(self.n["src/components/CartSummary.tsx"]["dependent"])
        links = {(e["from"], e["to"]) for e in self.g["imports"]}
        self.assertIn(("src/components/CartSummary.tsx", "src/lib/cart.ts"), links)
        self.assertNotIn("migrations/001_init.sql", self.g["stats"]["untested"])  # not code a test imports
        self.assertEqual(self.g["stats"]["untested"], [])

    def test_an_edit_no_test_reaches_is_flagged(self):
        g = build("/r", FILES, {"/r/src/lib/money.ts": "edit"}, None, IMPORTERS)
        self.assertEqual(g["stats"]["untested"], ["src/lib/money.ts"])

    def test_stats(self):
        self.assertEqual({k: self.g["stats"][k] for k in ("visited", "read", "edited")},
                         {"visited": 2, "read": 1, "edited": 2})  # the migration changed on disk, unopened

    def test_nothing_touched_gives_an_empty_map(self):
        g = build("/r", FILES, {}, None, IMPORTERS)
        self.assertEqual([n["id"] for n in g["nodes"]], [""])

    def test_layout_is_radial_and_inside_the_unit_circle(self):
        root = self.n[""]
        self.assertEqual((root["x"], root["y"]), (0, 0))
        for n in self.g["nodes"]:
            self.assertLessEqual(math.hypot(n["x"], n["y"]), 1.0001)
        self.assertLess(math.hypot(self.n["src"]["x"], self.n["src"]["y"]),
                        math.hypot(self.n["src/lib/cart.ts"]["x"], self.n["src/lib/cart.ts"]["y"]))


if __name__ == "__main__":
    unittest.main()
