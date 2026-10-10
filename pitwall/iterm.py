"""Everything Pitwall does to iTerm2: tab colours, badges, screen reads and keystrokes."""
from __future__ import annotations

import asyncio
import re

import iterm2

from pitwall import questions
from pitwall.colours import BADGES, TAB, is_our_badge, is_our_colour

# The first option of a Claude Code or Codex permission menu, with the cursor on it.
PROMPT_READY = re.compile(r"^\s*[❯›>]\s*1\.\s*Yes", re.M)

COLOURS = {name: iterm2.Color(*rgb) for name, rgb in TAB.items()}


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
        # Nothing is known about a tab until the first pass: it can carry a colour from before a
        # restart, so the first pass always writes, even when no signal is wanted.
        if self.applied.get(s["sid"]) == want:
            return
        if s["sid"] not in self.original:
            p = await session.async_get_profile()
            use, colour, badge = p.use_tab_color, p.tab_color, p.badge_text or ""
            # A tab can still carry Pitwall's colour or badge from before a restart. That is not
            # the user's own, so it is not what gets put back.
            if colour is not None and is_our_colour((colour.red, colour.green, colour.blue)):
                use, colour = False, None
            if is_our_badge(badge):
                badge = ""
            self.original[s["sid"]] = (use, colour, badge)
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


async def clear_stale(app, known):
    """Remove Pitwall's colour and badge from tabs that have no agent card any more."""
    for window in app.terminal_windows:
        for tab in window.tabs:
            for session in tab.sessions:
                if session.session_id in known:
                    continue
                p = await session.async_get_profile()
                colour = p.tab_color
                ours = p.use_tab_color and colour is not None and is_our_colour((colour.red, colour.green, colour.blue))
                if ours or is_our_badge(p.badge_text or ""):
                    change = iterm2.LocalWriteOnlyProfile()
                    if ours:
                        change.set_use_tab_color(False)
                    if is_our_badge(p.badge_text or ""):
                        change.set_badge_text("")
                    await session.async_set_profile_properties(change)


async def screen_text(session, last=None):
    contents = await session.async_get_screen_contents()
    # Cells a TUI skips with cursor moves read as NUL, not space (Claude Code draws its menus this way).
    lines = [contents.line(i).string.replace("\x00", " ") for i in range(contents.number_of_lines)]
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines[-last:] if last else lines)


async def answer(session, allow):
    """Answer a permission prompt. Returns an error message, or None when the keys went out."""
    if not PROMPT_READY.search(await screen_text(session, 40)):
        return "The permission prompt is not on screen, or another option is selected. Open the tab to answer."
    await session.async_send_text("\r" if allow else "\x1b")
    return None


async def answer_questions(session, asked, picks):
    """Answer an AskUserQuestion menu. Returns an error message, or None when the answers went in."""
    if not questions.menu_ready(await screen_text(session, 40), asked):
        return "The question menu is not on screen, or it is part answered. Open the tab to answer."
    for key in questions.keys(asked, picks):
        await session.async_send_text(key)
        await asyncio.sleep(0.15)  # the menu redraws after each key
    if not questions.needs_submit(asked):
        return None
    await asyncio.sleep(0.3)
    if not questions.review_ready(await screen_text(session, 40)):
        return "The answers went in, but the Submit page did not show. Open the tab to finish."
    await session.async_send_text("\r")
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
