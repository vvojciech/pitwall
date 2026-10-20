import json
import os
import time
import unittest

from pitwall.activity import codex_limits, summarize

os.environ["TZ"] = "UTC"
time.tzset()


def rec(ts, **kw):
    return json.dumps(dict({"timestamp": f"2026-10-10T{ts}Z", "cwd": "/w/shop/.claude/worktrees/feat"}, **kw))


def assistant(ts, msg_id, blocks, out=10, sidechain=False):
    return rec(ts, type="assistant", isSidechain=sidechain, message={"id": msg_id, "content": blocks, "usage": {
        "input_tokens": 1, "cache_creation_input_tokens": 100, "cache_read_input_tokens": 1000, "output_tokens": out}})


CLAUDE = [
    rec("08:00:00", type="user", message={"content": "Fix the login"}),
    assistant("08:00:30", "m1", [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/w/shop/a.ts"}}]),
    assistant("08:00:31", "m1", [{"type": "text", "text": "same message again"}]),  # repeated message id
    rec("08:01:00", type="user", message={"content": [{"type": "tool_result", "content": "ok"}]}),
    assistant("08:02:00", "m2", [{"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}},
                                  {"type": "tool_use", "name": "Write", "input": {"file_path": "/w/shop/a.ts"}}]),
    rec("08:03:00", type="user", isMeta=True, message={"content": "<local-command-stdout>x"}),
    rec("09:00:00", type="user", message={"content": [{"type": "text", "text": "Next"}, {"type": "image"}]}),
    assistant("09:00:20", "m3", [{"type": "text", "text": "Done"}]),
    "not json",
]

CODEX = [
    json.dumps({"timestamp": "2026-10-10T10:00:00Z", "type": "session_meta", "payload": {"cwd": "/w/api"}}),
    json.dumps({"timestamp": "2026-10-10T10:00:01Z", "type": "response_item", "payload": {
        "type": "message", "role": "user", "content": [{"type": "input_text", "text": "Add a dark mode"}]}}),
    json.dumps({"timestamp": "2026-10-10T10:00:40Z", "type": "response_item", "payload": {
        "type": "custom_tool_call", "name": "apply_patch", "input": "*** Update File: src/theme.ts\n"}}),
    json.dumps({"timestamp": "2026-10-10T10:01:00Z", "type": "event_msg", "payload": {
        "type": "token_count", "info": {"total_token_usage": {"total_tokens": 5000}},
        "rate_limits": {"primary": {"used_percent": 12.0, "window_minutes": 300, "resets_at": 1791638445},
                        "secondary": {"used_percent": 3.0, "window_minutes": 10080, "resets_at": 1791966425},
                        "credits": {"has_credits": True, "unlimited": False, "balance": "12"}}}}),
    json.dumps({"timestamp": "2026-10-10T10:02:00Z", "type": "event_msg", "payload": {
        "type": "token_count", "info": {"total_token_usage": {"total_tokens": 8000}}}}),
]


class ActivityTests(unittest.TestCase):
    def test_claude_day(self):
        (row,) = summarize(CLAUDE, "claude")
        self.assertEqual((row["day"], row["project"], row["agent"]), ("2026-10-10", "shop", "claude"))
        self.assertEqual(row["prompts"], 2)
        self.assertEqual(row["commands"], 1)
        self.assertEqual(row["files"], 1)
        self.assertEqual(row["tokens"], 3 * 1111)  # m1 once, m2, m3
        self.assertEqual(row["active"], 180 + 20)  # 08:00-08:03, then 09:00-09:00:20; the hour gap is idle

    def test_codex_day(self):
        (row,) = summarize(CODEX, "codex")
        self.assertEqual((row["project"], row["prompts"], row["files"], row["tokens"]), ("api", 1, 1, 8000))
        self.assertEqual(row["active"], 120)

    def test_codex_limits(self):
        limits = codex_limits(CODEX)
        self.assertEqual(limits["five_hour"], {"used": 12.0, "resets_at": 1791638445, "window": 18000})
        self.assertEqual(limits["week"]["window"], 604800)
        self.assertEqual(limits["week"], {"used": 3.0, "resets_at": 1791966425, "window": 604800})
        self.assertEqual(limits["credits"], {"has_credits": True, "unlimited": False, "balance": "12"})


if __name__ == "__main__":
    unittest.main()


class InstalledTests(unittest.TestCase):
    def test_only_agents_with_a_home_folder_are_listed(self):
        import tempfile
        from pathlib import Path
        from pitwall.usage import installed
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            self.assertEqual(installed(home), ["claude"])
            (home / ".codex").mkdir()
            self.assertEqual(installed(home), ["claude", "codex"])
