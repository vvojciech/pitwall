"""Everything Pitwall does to iTerm2: tab colours, badges, screen reads and keystrokes."""
from __future__ import annotations

import re

import iterm2

# The first option of a Claude Code or Codex permission menu, with the cursor on it.
PROMPT_READY = re.compile(r"^\s*[❯›>]\s*1\.\s*Yes", re.M)

COLOURS = {
    "waiting": iterm2.Color(232, 163, 61),
    "done": iterm2.Color(86, 182, 120),
    "failed": iterm2.Color(226, 86, 74),
}
BADGES = {"waiting_permission": "Needs you", "waiting_input": "Waiting"}


def signal_for(s, unseen):
    """The tab colour key for a session, or None for the profile's own colour."""
    if s["state"] in ("waiting_permission", "waiting_input"):
        return "waiting"
    if s["state"] in ("done", "failed") and s["sid"] in unseen:
        return s["state"]
    return None


class Tabs:
    """Applies tab colour and badge, and puts the profile's own values back afterwards."""

    def __init__(self, app):
        self.app = app
        self.applied = {}  # sid -> (colour key, badge)
        self.original = {}  # sid -> (use_tab_color, tab_color, badge_text)

    async def show(self, s, unseen):
        session = self.app.get_session_by_id(s["sid"])
        if session is None:
            return
        want = (signal_for(s, unseen), BADGES.get(s["state"]))
        if self.applied.get(s["sid"], (None, None)) == want:
            return
        if s["sid"] not in self.original:
            p = await session.async_get_profile()
            self.original[s["sid"]] = (p.use_tab_color, p.tab_color, p.badge_text or "")
        use, colour, badge = self.original[s["sid"]]
        change = iterm2.LocalWriteOnlyProfile()
        if want[0]:
            change.set_tab_color(COLOURS[want[0]])
            change.set_use_tab_color(True)
        else:
            change.set_use_tab_color(bool(use))
            if colour is not None:
                change.set_tab_color(colour)
        change.set_badge_text(want[1] or badge)
        await session.async_set_profile_properties(change)
        self.applied[s["sid"]] = want


async def screen_text(session, last=None):
    contents = await session.async_get_screen_contents()
    lines = [contents.line(i).string for i in range(contents.number_of_lines)]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines[-last:] if last else lines)


async def answer(session, allow):
    """Answer a permission prompt. Returns an error message, or None when the keys went out."""
    if not PROMPT_READY.search(await screen_text(session, 40)):
        return "The permission prompt is not on screen, or another option is selected. Open the tab to answer."
    await session.async_send_text("\r" if allow else "\x1b")
    return None


async def focus(app, session):
    """Show the session and give it keyboard focus, away from the Pitwall panel.

    iTerm2 moves keyboard focus only when the active pane or the selected tab changes
    (PTYTab setActiveSession, PseudoTerminal didSelectTabViewItem). To focus the pane that is
    already active, select a sibling first, then the target.
    """
    await app.async_activate(raise_all_windows=False, ignoring_other_apps=True)
    tab, window = session.tab, session.window
    current_tab = window and window.current_tab
    current = tab and tab.current_session
    if current_tab and current and current_tab.tab_id == tab.tab_id and current.session_id == session.session_id:
        sibling = next((s for s in tab.sessions if s.session_id != session.session_id), None)
        other_tab = next((t for t in window.tabs if t.tab_id != tab.tab_id), None)
        if sibling:
            await sibling.async_activate(select_tab=True, order_window_front=True)
        elif other_tab:
            await other_tab.async_activate(order_window_front=True)
        # ponytail: a window with one tab and one pane keeps the focus where it is
    await session.async_activate(select_tab=True, order_window_front=True)
