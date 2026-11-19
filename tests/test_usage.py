import json
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from pitwall import usage
from pitwall.usage import claude_limits, windows_left

NOW = 1_791_760_000


def snap(five=None, week=None, changed=0):
    w = lambda p: p and {"used_percentage": p[0], "resets_at": p[1]}
    return changed, {"five_hour": w(five), "seven_day": w(week)}


class ClaudeLimitsTests(unittest.TestCase):
    def test_idle_session_with_old_limits_does_not_win(self):
        # An idle session re-renders its status line with the limits of its last reply.
        # Its limits did not change, so its change time stays old.
        fresh = snap(five=(3, NOW + 3600), week=(84, NOW + 86400), changed=NOW - 60)
        stale = snap(five=None, week=(69, NOW + 86400), changed=NOW - 3600)
        out = claude_limits([fresh, stale], NOW)
        self.assertEqual(out["five_hour"]["used"], 3)
        self.assertEqual(out["week"], {"used": 84, "resets_at": NOW + 86400, "window": 604800})

    def test_a_reset_week_beats_a_higher_use_seen_before_it(self):
        # A limit reset keeps the reset time and drops the use.
        before = snap(week=(90, NOW + 86400), changed=NOW - 86400)
        after = snap(week=(36, NOW + 86400), changed=NOW - 60)
        self.assertEqual(claude_limits([after, before], NOW)["week"]["used"], 36)

    def test_a_newer_window_beats_a_higher_use_in_an_older_one(self):
        out = claude_limits([snap(five=(33, NOW - 60)), snap(five=(2, NOW + 600))], NOW)
        self.assertEqual(out["five_hour"]["used"], 2)

    def test_an_expired_window_shows_nothing(self):
        out = claude_limits([snap(five=(33, NOW - 60), week=(10, NOW + 60))], NOW)
        self.assertIsNone(out["five_hour"])
        self.assertEqual(out["week"]["used"], 10)

    def test_no_limits_gives_none(self):
        self.assertIsNone(claude_limits([(0, {}), (0, None)], NOW))


class WindowsLeftTests(unittest.TestCase):
    def test_counts_the_five_hour_windows_until_the_week_resets(self):
        # The current window, then five more in the 25 hours after it ends.
        limits = {"five_hour": {"resets_at": NOW + 3600}, "week": {"resets_at": NOW + 3600 + 25 * 3600}}
        self.assertEqual(windows_left(limits), 6)

    def test_a_missing_window_gives_none(self):
        self.assertIsNone(windows_left({"five_hour": None, "week": {"resets_at": NOW}}))
        self.assertIsNone(windows_left(None))


def reply(model, tokens):
    now = datetime.now(timezone.utc).isoformat()
    return json.dumps({"type": "assistant", "timestamp": now, "cwd": "/w/shop",
                       "message": {"id": model, "model": model, "usage": {"output_tokens": tokens}}})


class ActivityCacheTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name)
        self.cache = self.home / "activity-cache.json"
        for target, name, value in ((usage, "CACHE", self.cache), (usage, "LIMITS_SEEN", self.home / "seen.json"),
                                    (usage.config, "HOME", self.home)):  # never the real ~/.pitwall
            patcher = mock.patch.object(target, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.transcript = self.home / ".claude/projects/-w-shop/s.jsonl"
        self.transcript.parent.mkdir(parents=True)
        self.transcript.write_text(reply("claude-opus-5-5", 300) + "\n" + reply("claude-fable-5-1", 100) + "\n")

    def test_today_splits_the_tokens_by_model_family(self):
        today = usage.report(self.home, days=1)["today"]
        self.assertEqual(today["tokens"], 400)
        self.assertEqual(today["models"], {"opus": 300, "fable": 100})

    def test_a_cache_entry_from_before_the_model_split_is_read_again(self):
        stat = self.transcript.stat()
        old_rows = [{"day": time.strftime("%Y-%m-%d"), "project": "shop", "agent": "claude", "active": 0,
                     "prompts": 0, "tokens": 400, "files": 0, "commands": 0}]
        self.cache.write_text(json.dumps({str(self.transcript): {"stamp": [stat.st_mtime, stat.st_size], "rows": old_rows}}))
        (row,) = usage.activity(self.home, days=1)
        self.assertEqual(row["models"], {"opus": 300, "fable": 100})
        self.assertEqual(usage.report(self.home, days=1)["today"]["models"], {"opus": 300, "fable": 100})

    def test_an_unchanged_transcript_comes_from_the_cache(self):
        usage.activity(self.home, days=1)
        with mock.patch.object(usage, "summarize") as summarize:
            (row,) = usage.activity(self.home, days=1)
        summarize.assert_not_called()
        self.assertEqual(row["models"], {"opus": 300, "fable": 100})


if __name__ == "__main__":
    unittest.main()
