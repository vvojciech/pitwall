"""Runs review loops against iTerm2: starts the reviewer, reacts to Stop events, delivers messages."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path

from pitwall import snapshot, timeline
from pitwall.loop import new_loop, on_stop

BUSY = ("working", "waiting_permission")


class Loops:
    def __init__(self, features):
        self.f, self.d = features, features.d

    def writer_of(self, reviewer_sid):
        return next((s for s in self.d.sessions.values()
                     if s.get("loop") and s["loop"]["reviewer"] == reviewer_sid), None)

    async def start(self, s, reviewer_agent, max_rounds, auto):
        text = await asyncio.to_thread(self.f.handoff_text, s, "review")
        _, reviewer_sid = await self.f.launch(s["sid"], reviewer_agent, s["cwd"], text,
                                              f"review-{os.path.basename(s['cwd'])}")
        s["loop"] = new_loop(reviewer_sid, reviewer_agent, max_rounds, auto)
        s["loop"]["base"] = await asyncio.to_thread(self._tree, s)
        self.d.save()

    def _tree(self, s):
        snap = snapshot.take(s["cwd"]) if s.get("cwd") else None
        return snap and snap["tree"]

    async def on_stop(self, s, last_message):
        """Called for every Stop event. Advances the loop that s takes part in, if any."""
        writer, who = (s, "writer") if s.get("loop") else (self.writer_of(s["sid"]), "reviewer")
        if not writer or writer["loop"]["phase"] not in ("reviewing", "fixing"):
            return
        loop = writer["loop"]
        if loop.get("pending"):  # a message waits for delivery; this Stop may free its target
            if loop["auto"]:
                await self.send(writer)
            return
        reply = last_message or await asyncio.to_thread(timeline.read_last_reply, s, Path.home())

        def diff():
            root = snapshot.repo_root(writer["cwd"])
            return snapshot.diff(root, loop["base"]) if root and loop.get("base") else ""

        to, text = await asyncio.to_thread(on_stop, loop, who, reply, diff)
        if to:
            loop["pending"] = {"to": to, "text": text}
            if loop["auto"]:
                await self.send(writer)
        self.d.save()
        self.d.changed(writer)

    async def send(self, writer):
        """Deliver the pending message. Returns an error message, or None."""
        loop = writer["loop"]
        pending = loop.get("pending")
        if not pending:
            return "Nothing to send."
        target_sid = writer["sid"] if pending["to"] == "writer" else loop["reviewer"]
        session = self.d.app.get_session_by_id(target_sid)
        if session is None:
            return "The other agent's tab is gone. Stop the loop."
        target = self.d.sessions.get(target_sid)
        if target and target["state"] in BUSY:
            return "That agent is in the middle of a turn. Send when it stops."
        if pending["to"] == "writer":
            loop["base"] = await asyncio.to_thread(self._tree, writer)  # the next round's diff starts here
        await self.f.paste(session, pending["text"])
        loop["pending"] = None
        self.d.save()
        return None

    def stop(self, writer):
        writer["loop"]["phase"] = "stopped"
        writer["loop"]["pending"] = None
        self.d.save()
