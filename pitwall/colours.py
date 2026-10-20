"""The tab colours and badges Pitwall sets, and a check that tells them apart from a user's own."""
from __future__ import annotations

# Dark on purpose: a tab should hint, not shout.
TAB = {
    "waiting": (74, 52, 16),   # dark amber: the agent needs you
    "done": (18, 52, 32),      # dark green: finished while you were elsewhere
    "failed": (70, 24, 22),    # dark red: the turn failed
}
# Colours earlier versions set. A tab can still carry one after an update.
LEGACY = ((232, 163, 61), (86, 182, 120), (226, 86, 74))
BADGES = {"waiting_permission": "Needs you", "waiting_input": "Waiting"}


def want_for(s, unseen, prefs):
    """(tab colour key, badge) a session should show, each None for the profile's own value."""
    colour = None
    if s["state"] in ("waiting_permission", "waiting_input"):
        colour = "waiting"
    elif s["state"] in ("done", "failed") and s["sid"] in unseen:
        colour = s["state"]
    return (colour if prefs["tab_colours"] else None,
            BADGES.get(s["state"]) if prefs["tab_badges"] else None)


def is_our_colour(rgb, tolerance=3):
    """True for a colour Pitwall sets or has set, so it is never taken as the user's own."""
    return any(all(abs(a - b) <= tolerance for a, b in zip(rgb, ours)) for ours in (*TAB.values(), *LEGACY))


def is_our_badge(text):
    return text in BADGES.values()
