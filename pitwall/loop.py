"""Review loops: one agent reviews another's work, round after round, until it approves.

The state is a dict on the writer's session, so it is saved with the rest of the state.
Phases: reviewing, fixing, approved, limit (round limit reached), stopped.
"""
from __future__ import annotations

import re

VERDICT = re.compile(r"\b(NOT APPROVED|CHANGES NEEDED|APPROVED)\b")
ASK_VERDICT = "End your answer with APPROVED or CHANGES NEEDED."


def new_loop(reviewer_sid, reviewer_agent, max_rounds=3, auto=False):
    return {"reviewer": reviewer_sid, "reviewer_agent": reviewer_agent, "round": 1, "max": max_rounds,
            "auto": auto, "phase": "reviewing", "pending": None, "base": None}


def verdict(text):
    """'approved' when the last verdict in the text is APPROVED, else 'changes'."""
    found = VERDICT.findall(text or "")
    return "approved" if found and found[-1] == "APPROVED" else "changes"


def writer_message(review, loop):
    return (f"A reviewer checked your work (review round {loop['round']} of {loop['max']}). "
            f"Fix the problems below, then stop. If you disagree with a point, say why in your answer.\n\n"
            f"{review.strip()}")


def reviewer_message(diff, loop):
    body = f"```diff\n{diff.strip()}\n```" if diff.strip() else "The writer changed no files."
    return (f"Review round {loop['round']} of {loop['max']}. The writer answered your review and changed "
            f"the files below. Check that each problem is fixed and that nothing new broke. "
            f"Do not edit any file. {ASK_VERDICT}\n\n{body}")


def on_stop(loop, who, last_message, diff):
    """Advance the loop when 'writer' or 'reviewer' stops. Returns (send_to, text), or (None, None).

    `diff` is a function, so the diff is made only when the writer's round is over.
    """
    if who == "reviewer" and loop["phase"] == "reviewing":
        if verdict(last_message) == "approved":
            loop["phase"] = "approved"
            return None, None
        loop["phase"] = "fixing"
        return "writer", writer_message(last_message or "(The reviewer gave no details.)", loop)
    if who == "writer" and loop["phase"] == "fixing":
        if loop["round"] >= loop["max"]:
            loop["phase"] = "limit"
            return None, None
        loop["round"] += 1
        loop["phase"] = "reviewing"
        return "reviewer", reviewer_message(diff(), loop)
    return None, None
