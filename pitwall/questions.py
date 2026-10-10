"""Claude Code's AskUserQuestion menu: what the card shows, and the keys that answer it.

Measured on Claude Code 2.1.283: a digit picks an option. In a single-select question the
digit also moves to the next question; in a multi-select question it toggles the option and
Tab moves on. With two or more questions, or any multi-select question, a review page comes
last, with "Submit answers" selected. One single-select question submits at once.
"""
from __future__ import annotations

import re

MAX_QUESTIONS = 4
MAX_OPTIONS = 9  # one digit each


def _text(value, limit):
    return str(value or "").strip()[:limit]


def parse(tool_input):
    """The questions in an AskUserQuestion tool input, or None if the panel cannot answer them."""
    raw = tool_input.get("questions") if isinstance(tool_input, dict) else None
    if not isinstance(raw, list) or not 0 < len(raw) <= MAX_QUESTIONS:
        return None
    out = []
    for q in raw:
        options = q.get("options") if isinstance(q, dict) else None
        if not isinstance(options, list) or not 0 < len(options) <= MAX_OPTIONS:
            return None
        out.append({
            "question": _text(q.get("question"), 300),
            "header": _text(q.get("header"), 40),
            "multi": q.get("multiSelect") is True,
            "options": [{"label": _text(o.get("label"), 120), "description": _text(o.get("description"), 300)}
                        for o in options if isinstance(o, dict)],
        })
    return out


def problem(questions, picks):
    """Why the picks cannot answer the questions, or None when they can."""
    if not isinstance(picks, list) or len(picks) != len(questions):
        return "Answer every question."
    for q, chosen in zip(questions, picks):
        if not isinstance(chosen, list) or not chosen or len(set(chosen)) != len(chosen):
            return "Answer every question."
        if not q["multi"] and len(chosen) != 1:
            return "Pick one option for each single-choice question."
        if any(type(i) is not int or not 0 <= i < len(q["options"]) for i in chosen):
            return "That option does not exist."
    return None


def keys(questions, picks):
    """The keys to type, one string per key press."""
    out = []
    for q, chosen in zip(questions, picks):
        out += [str(i + 1) for i in sorted(chosen)]
        if q["multi"]:
            out.append("\t")
    return out


def needs_submit(questions):
    return len(questions) > 1 or any(q["multi"] for q in questions)


def menu_ready(screen, questions):
    """True when the menu is untouched: first question shown, nothing answered, option 1 selected."""
    answered = any(q["header"] and f"☒ {q['header']}" in screen for q in questions)
    # A long question wraps at the pane width, so match its start only.
    return (not answered and questions[0]["question"][:30] in screen
            and re.search(r"^\s*❯\s*1\.", screen, re.M) is not None)


def review_ready(screen):
    return re.search(r"^\s*❯\s*1\.\s*Submit answers", screen, re.M) is not None
