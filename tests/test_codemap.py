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
        self.g = build("/r", FILES, touched, "/r/src/lib/cart.ts", IMPORTERS, "overview")
        self.n = nodes(self.g)

    def test_overview_shows_shallow_folders_and_touched_files(self):
        self.assertIn("src/components", self.n)
        self.assertIn("docs", self.n)
        self.assertNotIn("docs/deep/a", self.n)  # deep folders stay folded
        self.assertNotIn("src/lib/money.ts", self.n)  # untouched files stay folded
        self.assertEqual(self.n["src/lib/cart.ts"]["touch"], "edit")
        self.assertTrue(self.n["src/lib/cart.ts"]["current"])
        self.assertEqual(self.n["src"]["count"], 6)

    def test_files_outside_the_repo_are_left_out(self):
        self.assertFalse(any("elsewhere" in i for i in self.n))

    def test_blast_radius(self):
        self.assertTrue(self.n["src/components/CartSummary.tsx"]["dependent"])
        links = {(e["from"], e["to"]) for e in self.g["imports"]}
        self.assertIn(("src/components/CartSummary.tsx", "src/lib/cart.ts"), links)
        self.assertEqual(self.g["stats"]["untested"], [])  # tests/cart.test.ts imports it

    def test_an_edit_no_test_reaches_is_flagged(self):
        g = build("/r", FILES, {"/r/src/lib/money.ts": "edit"}, None, IMPORTERS, "overview")
        self.assertEqual(g["stats"]["untested"], ["src/lib/money.ts"])

    def test_stats(self):
        self.assertEqual({k: self.g["stats"][k] for k in ("files", "visited", "edited")},
                         {"files": 12, "visited": 2, "edited": 1})

    def test_layout_is_radial_and_inside_the_unit_circle(self):
        root = self.n[""]
        self.assertEqual((root["x"], root["y"]), (0, 0))
        for n in self.g["nodes"]:
            self.assertLessEqual(math.hypot(n["x"], n["y"]), 1.0001)
        self.assertLess(math.hypot(self.n["src"]["x"], self.n["src"]["y"]),
                        math.hypot(self.n["src/lib/cart.ts"]["x"], self.n["src/lib/cart.ts"]["y"]))

    def test_files_mode_shows_the_siblings_of_touched_files(self):
        n = nodes(build("/r", FILES, {"/r/src/lib/cart.ts": "edit"}, None, IMPORTERS, "files"))
        self.assertIn("src/lib/money.ts", n)


if __name__ == "__main__":
    unittest.main()
