import tempfile
import unittest
from pathlib import Path

from pitwall.memory import context_for, slug


class MemoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        mem = self.home / ".claude/projects" / slug("/work/shop.app") / "memory"
        mem.mkdir(parents=True)
        (mem / "MEMORY.md").write_text("- [Deploy](deploy.md) - run make ship\n")
        codex = self.home / ".codex/memories"
        codex.mkdir(parents=True)
        (codex / "tests.md").write_text("Run the tests with pnpm, never npm.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_slug_matches_claude_code(self):
        self.assertEqual(slug("/Users/w/bits.bitbybit.pl"), "-Users-w-bits-bitbybit-pl")

    def test_codex_gets_claudes_notes_for_the_project(self):
        text = context_for("codex", "/work/shop.app/src", self.home)
        self.assertIn("run make ship", text)
        self.assertIn("Claude Code", text)
        self.assertIn(str(self.home / ".claude/projects" / slug("/work/shop.app") / "memory"), text)

    def test_claude_gets_codexs_memories(self):
        text = context_for("claude", "/work/shop.app", self.home)
        self.assertIn("never npm", text)
        self.assertIn("out of date", text)

    def test_no_notes_gives_none(self):
        self.assertIsNone(context_for("codex", "/elsewhere", self.home))

    def test_long_notes_are_cut(self):
        (self.home / ".codex/memories/big.md").write_text("x" * 50_000)
        self.assertLess(len(context_for("claude", "/work", self.home)), 9_000)


if __name__ == "__main__":
    unittest.main()
