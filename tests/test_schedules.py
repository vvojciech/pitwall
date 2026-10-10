import unittest
from datetime import datetime

from pitwall.schedules import GRACE, next_fire, parse, stop_message, view


def ts(*args):
    """Local time as epoch seconds, the way Claude Code reads a cron expression."""
    return datetime(*args).timestamp()


class ParseTests(unittest.TestCase):
    def test_fields(self):
        minutes, hours, dom, months, dow, _, _ = parse("*/15 1-5 1,15 * 1-5")
        self.assertEqual(minutes, {0, 15, 30, 45})
        self.assertEqual(hours, {1, 2, 3, 4, 5})
        self.assertEqual(dom, {1, 15})
        self.assertEqual(len(months), 12)
        self.assertEqual(dow, {1, 2, 3, 4, 5})

    def test_stepped_range(self):
        self.assertEqual(parse("5-20/5 * * * *")[0], {5, 10, 15, 20})

    def test_sunday_is_0_and_7(self):
        self.assertEqual(parse("0 0 * * 7")[4], {0})

    def test_invalid(self):
        for bad in ("", "* * * *", "61 * * * *", "* * * * * *", "a * * * *", "*/0 * * * *", "5-1 * * * *"):
            self.assertIsNone(parse(bad), bad)


class NextFireTests(unittest.TestCase):
    def test_daily(self):
        self.assertEqual(next_fire("7 3 * * *", ts(2026, 10, 10, 21, 53)), ts(2026, 10, 11, 3, 7))

    def test_every_five_minutes_is_strictly_after(self):
        self.assertEqual(next_fire("*/5 * * * *", ts(2026, 10, 10, 12, 5)), ts(2026, 10, 10, 12, 10))

    def test_one_shot_pinned_date(self):
        self.assertEqual(next_fire("13 4 11 10 *", ts(2026, 10, 10, 22, 0)), ts(2026, 10, 11, 4, 13))

    def test_year_end(self):
        self.assertEqual(next_fire("0 0 1 1 *", ts(2026, 12, 31, 23, 59)), ts(2027, 1, 1, 0, 0))

    def test_month_without_the_day(self):
        self.assertEqual(next_fire("0 9 31 * *", ts(2026, 11, 1, 0, 0)), ts(2026, 12, 31, 9, 0))

    def test_weekdays(self):  # 2026-10-10 is a Saturday
        self.assertEqual(next_fire("57 8 * * 1-5", ts(2026, 10, 10, 9, 0)), ts(2026, 10, 12, 8, 57))

    def test_day_of_month_or_day_of_week(self):  # both restricted: either one matches
        self.assertEqual(next_fire("0 12 15 * 1", ts(2026, 10, 10, 0, 0)), ts(2026, 10, 12, 12, 0))

    def test_impossible_and_invalid(self):
        self.assertIsNone(next_fire("0 0 30 2 *", ts(2026, 1, 1)))
        self.assertIsNone(next_fire("nonsense", ts(2026, 1, 1)))


def session(*jobs, wakeup=None):
    return {"schedules": {j["id"]: j for j in jobs}, "wakeup": wakeup}


def job(id, schedule, prompt="check", recurring=True, first_seen=0.0, **kw):
    return dict({"id": id, "schedule": schedule, "prompt": prompt, "recurring": recurring,
                 "first_seen": first_seen}, **kw)


class ViewTests(unittest.TestCase):
    NOW = ts(2026, 10, 10, 12, 0)

    def test_kinds_and_order(self):
        rows = view(session(job("a", "7 3 * * *", "nightly"),
                            job("b", "13 12 10 10 *", "one shot", recurring=False),
                            job("c", "30 12 10 10 *", "/loop check the time", recurring=False)), self.NOW)
        self.assertEqual([r["id"] for r in rows], ["b", "c", "a"])
        self.assertEqual([r["kind"] for r in rows], ["once", "loop", "repeats"])
        self.assertEqual(rows[1]["text"], "check the time")

    def test_wakeup_time_wins(self):
        s = session(job("c", "30 12 10 10 *", "/loop x", recurring=False, at=self.NOW + 42))
        self.assertEqual(view(s, self.NOW)[0]["next"], self.NOW + 42)

    def test_a_late_fire_shows_due_then_rolls_forward(self):
        s = session(job("a", "0 * * * *", first_seen=self.NOW - 3600))
        self.assertEqual(view(s, self.NOW + 60)[0]["next"], self.NOW)  # due, inside the grace
        self.assertEqual(view(s, self.NOW + GRACE + 60)[0]["next"], self.NOW + 3600)

    def test_a_seen_fire_moves_to_the_next(self):
        s = session(job("a", "0 * * * *", first_seen=self.NOW - 3600, last_fired=self.NOW + 30))
        self.assertEqual(view(s, self.NOW + 60)[0]["next"], self.NOW + 3600)

    def test_recurring_jobs_expire_after_seven_days(self):
        rows = view(session(job("a", "0 * * * *", first_seen=self.NOW - 100), job("b", "0 9 11 10 *", recurring=False)),
                    self.NOW)
        self.assertEqual(rows[0]["expires"], self.NOW - 100 + 7 * 86400)
        self.assertIsNone(rows[1]["expires"])

    def test_a_job_that_expires_first_counts_down_to_its_final_run(self):  # it fires once more, then goes
        row = view(session(job("a", "7 3 * * *", first_seen=self.NOW - 7 * 86400 + 3600)), self.NOW)[0]
        self.assertEqual(row["next"], self.NOW + 3600)
        self.assertTrue(row["final"])
        self.assertFalse(view(session(job("b", "0 * * * *", first_seen=self.NOW)), self.NOW)[0]["final"])

    def test_bad_schedule_has_no_countdown(self):
        row = view(session(job("a", "every tuesday")), self.NOW)[0]
        self.assertIsNone(row["next"])
        self.assertEqual(row["human"], "every tuesday")

    def test_empty(self):
        self.assertEqual(view({}, self.NOW), [])

    def test_stopping_shows(self):
        self.assertTrue(view(session(job("a", "0 * * * *", stopping=True)), self.NOW)[0]["stopping"])


class DescribeTests(unittest.TestCase):
    def test_common_shapes(self):
        from pitwall.schedules import describe
        self.assertEqual(describe("*/5 * * * *"), "Every 5 minutes")
        self.assertEqual(describe("* * * * *"), "Every minute")
        self.assertEqual(describe("7 * * * *"), "Every hour at :07")
        self.assertEqual(describe("7 3 * * *"), "Every day at 03:07")
        self.assertEqual(describe("57 8 * * 1-5"), "Weekdays at 08:57")
        self.assertEqual(describe("13 4 11 10 *"), "Once, 11 Oct at 04:13")
        self.assertEqual(describe("0 9 * * 1"), "0 9 * * 1")  # anything else stays as written

    def test_rows_use_it_and_wakeups_say_who_timed_them(self):
        rows = view(session(job("a", "7 3 * * *"), job("w", "1 0 1 1 *", "/loop x", recurring=False, at=1.0)), 0)
        self.assertEqual({r["id"]: r["human"] for r in rows}, {"a": "Every day at 03:07", "w": "One wake-up, timed by Claude"})
        self.assertEqual(view(session(job("b", "7 3 * * *", human="Daily, 3:07 AM")), 0)[0]["human"], "Daily, 3:07 AM")


class StopMessageTests(unittest.TestCase):
    def test_a_job_is_deleted_by_id(self):
        text = stop_message(job("a3ecd9af", "7 3 * * *", "nightly check"))
        self.assertIn("CronDelete", text)
        self.assertIn("a3ecd9af", text)
        self.assertNotIn("ScheduleWakeup", text)

    def test_a_loop_also_stops_its_wakeups(self):
        text = stop_message(job("84336790", "56 21 * * *", "/loop check the time", recurring=False))
        self.assertIn("84336790", text)
        self.assertIn("ScheduleWakeup", text)
        self.assertIn("stop", text)
