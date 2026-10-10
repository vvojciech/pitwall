import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from pitwall import context


class ContextTests(unittest.TestCase):
    def test_claude_status(self):
        status = {"context_window": {"used_percentage": 93, "context_window_size": 1000000,
                                     "current_usage": {"input_tokens": 2, "cache_creation_input_tokens": 76,
                                                       "cache_read_input_tokens": 927381}}}
        self.assertEqual(context.from_claude(status), {"used": 93, "size": 1000000, "tokens": 927459})

    def test_claude_status_without_context(self):
        self.assertIsNone(context.from_claude({"model": {}}))

    def test_codex_token_count(self):
        lines = [json.dumps({"type": "event_msg", "payload": {"type": "token_count", "info": {
            "last_token_usage": {"total_tokens": 24566}, "model_context_window": 258400}}})]
        self.assertEqual(context.from_codex(lines), {"used": 10, "size": 258400, "tokens": 24566})

    def test_codex_without_numbers(self):
        self.assertIsNone(context.from_codex(['{"type": "session_meta", "payload": {}}', "not json"]))

    def test_for_a_claude_session_reads_its_own_status_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp, "status")
            folder.mkdir()
            (folder / "s1.json").write_text(json.dumps({"context_window": {"used_percentage": 40, "context_window_size": 200000}}))
            s = {"agent": "claude", "agent_session": "s1"}
            self.assertEqual(context.for_session(s, Path(tmp), Path(tmp))["used"], 40)
            self.assertIsNone(context.for_session({"agent": "claude", "agent_session": "nope"}, Path(tmp), Path(tmp)))
            self.assertIsNone(context.for_session({"agent": "claude", "agent_session": "../s1"}, Path(tmp), Path(tmp)))


if __name__ == "__main__":
    unittest.main()
