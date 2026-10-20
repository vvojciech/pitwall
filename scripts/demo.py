#!/usr/bin/env python3
"""Serve the Pitwall UI with invented data, for screenshots and UI work. No daemon, no iTerm2.

    python3 scripts/demo.py [port]      then open http://127.0.0.1:47821/?t=demo
"""
import http.server
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pitwall.codemap import build  # noqa: E402
from pitwall.schedules import view  # noqa: E402
from pitwall.settings import DEFAULTS, FEATURES  # noqa: E402

WEB = os.path.join(ROOT, "pitwall", "web")
NOW = time.time()
SHOP = "/Users/demo/code/acme-shop"
FILES = [f"src/{p}" for p in ("app/page.tsx", "app/layout.tsx", "app/cart/page.tsx", "app/api/cart/route.ts",
         "app/api/checkout/route.ts", "components/CartSummary.tsx", "components/Button.tsx", "components/Price.tsx",
         "components/Header.tsx", "lib/cart.ts", "lib/money.ts", "lib/db.ts")] + [
         "tests/cart.test.ts", "tests/money.test.ts", "migrations/001_init.sql", "migrations/002_orders.sql",
         "public/logo.svg", "package.json", "next.config.js", "scripts/seed.ts"]
IMPORTERS = {"src/lib/cart.ts": ["src/components/CartSummary.tsx", "src/app/api/cart/route.ts", "tests/cart.test.ts"],
             "src/components/CartSummary.tsx": ["src/app/cart/page.tsx"]}


def card(sid, cwd, agent, state, task, action=None, ago=0, done=None, **kw):
    return dict({"sid": sid, "agent": agent, "agent_session": f"s{sid}", "cwd": cwd, "state": state, "task": task,
                 "action": action, "started": NOW - ago, "finished": done and NOW - done, "permission": None,
                 "error": None, "updated": NOW, "title": "", "focused": False, "unseen": False, "can_undo": True,
                 "can_redo": False}, **kw)


SESSIONS = [
    card("1", SHOP, "claude", "waiting_permission", "Show the cart total with tax and shipping", "Edit CartSummary.tsx",
         252, permission="Bash npm run db:migrate", focused=True,
         schedules=view({"schedules": {"r1": {"id": "r1", "schedule": time.strftime("%M %H %d %m *", time.localtime(NOW + 5520)),
                                              "recurring": False, "prompt": "Remind me to check the staging migration",
                                              "first_seen": NOW - 60}}}, NOW)),
    card("2", "/Users/demo/code/billing-api", "codex", "working", "Retry failed webhooks with backoff", "Edit webhooks.ts", 75,
         name="Webhooks"),
    card("3", "/Users/demo/code/docs-site", "claude", "done", "Write the upgrade guide for v3", None, 900, 140, unseen=True,
         background=[{"type": "shell", "status": "running", "description": "Docs dev server", "command": "npm run dev"},
                     {"type": "subagent", "status": "running", "description": "Check every link in the guide"}],
         schedules=view({"schedules": {
             "w1": {"id": "w1", "schedule": "0 0 1 1 *", "recurring": False, "prompt": "/loop check the deploy finished",
                    "at": NOW + 262, "reason": "Vercel builds take about four minutes"},
             "c1": {"id": "c1", "schedule": "7 3 * * *", "recurring": True, "prompt": "Re-run the link checker",
                    "human": "Every day at 3:07 AM", "first_seen": NOW - 7 * 86400 + 7380}}}, NOW),  # final run
         loop={"reviewer": "2", "reviewer_agent": "codex", "round": 1, "max": 3, "auto": False, "phase": "fixing",
               "pending": {"to": "writer", "text": "1. guide.md:41 says Node 18; v3 needs Node 20.\n\nCHANGES NEEDED"}}),
]
SESSIONS.insert(2, card("4", "/Users/demo/code/mobile", "claude", "waiting_input", "Add dark mode to the settings screen",
                       "AskUserQuestion", 40, questions=[
    {"question": "Which screens get dark mode first?", "header": "Scope", "multi": True, "options": [
        {"label": "Settings", "description": "The screen in the prompt"},
        {"label": "Home", "description": ""}, {"label": "Checkout", "description": "Has the most custom colours"}]},
    {"question": "Follow the system setting, or add a switch?", "header": "Control", "multi": False, "options": [
        {"label": "Follow the system (Recommended)", "description": "No new setting to explain"},
        {"label": "Add a switch", "description": "Light, dark or system, in Settings"}]}]))
SESSIONS.append(SESSIONS.pop(0))  # tab order: the waiting agent is in the last tab
CONTEXT = {"4": (12, 200000), "1": (34, 200000), "2": (83, 258400), "3": (94, 1000000)}  # one of each ring colour
for c in SESSIONS:
    used, size = CONTEXT[c["sid"]]
    c["context"] = {"used": used, "size": size, "tokens": size * used // 100}
FAILURES = [{"id": 1, "command": "npm run dev", "status": 1, "cwd": SHOP, "project": "acme-shop", "agent_sid": "1",
             "agent": "claude", "output": "Error: listen EADDRINUSE: address already in use :::3000",
             "busy": {"pid": 4211, "command": "node", "port": 3000, "project": "storefront"}}]


def activity(days):
    rows = []
    for i in range(days):
        day = time.strftime("%Y-%m-%d", time.localtime(NOW - i * 86400))
        for project, agent, hours in (("acme-shop", "claude", 3.1), ("billing-api", "codex", 1.4), ("docs-site", "claude", 0.8)):
            h = hours * (1 + 0.45 * ((i * 7 + len(project)) % 5 - 2) / 2)
            rows.append({"day": day, "project": project, "agent": agent, "active": int(h * 3600), "prompts": int(h * 9),
                         "tokens": int(h * 4.2e6), "files": int(h * 6), "commands": int(h * 40)})
    H5, WK = 5 * 3600, 7 * 86400
    limits = {"claude": {"five_hour": {"used": 64, "resets_at": NOW + 5400, "window": H5}, "week": {"used": 38, "resets_at": NOW + 300000, "window": WK}, "windows_left": 18},
              "codex": {"five_hour": {"used": 22, "resets_at": NOW + 9000, "window": H5}, "week": {"used": 81, "resets_at": NOW + 200000, "window": WK},
                        "credits": {"has_credits": True, "unlimited": False, "balance": "40"}, "windows_left": 40}}
    today = [r for r in rows if r["day"] == time.strftime("%Y-%m-%d")]
    return {"days": days, "rows": rows, "limits": limits,
            "today": {k: sum(r[k] for r in today) for k in ("active", "prompts", "tokens", "files", "commands")}}


def code_map(mode):
    touched = {f"{SHOP}/src/lib/cart.ts": "edit", f"{SHOP}/src/components/CartSummary.tsx": "edit",
               f"{SHOP}/src/lib/money.ts": "read", f"{SHOP}/README.md": "read"}
    changed = ["src/app/api/cart/route.ts"] + (["migrations/002_orders.sql", "scripts/seed.ts"] if mode == "uncommitted" else [])
    if mode == "uncommitted":
        touched = {}  # uncommitted shows what git sees, not what the agent opened
    g = build(SHOP, FILES, touched, f"{SHOP}/src/components/CartSummary.tsx", IMPORTERS, changed)
    g["stats"].update(added=19, removed=3)
    g.update(project="acme-shop", agent="claude", state="working", action="Edit CartSummary.tsx", truncated=False)
    return g


SETTINGS = dict(DEFAULTS)  # in memory: the demo never touches ~/.pitwall


def describe():
    return {"features": [{"key": k, "group": g, "label": label, "hint": hint, "on": SETTINGS[k], "locked": None}
                         for k, g, label, hint in FEATURES]}


ROUTES = {
    "/api/state": lambda q: {"now": time.time(), "sessions": SESSIONS, "failures": FAILURES, "settings": SETTINGS},
    "/api/settings": lambda q: describe(),
    "/api/ports": lambda q: {"ports": [{"pid": 4211, "port": 3000, "command": "node", "project": "storefront"},
                                       {"pid": 5120, "port": 5173, "command": "node", "project": "acme-shop"}]},
    "/api/races": lambda q: {"races": [], "projects": [SHOP]},
    "/api/activity": lambda q: activity(int(q.get("days", 7))),
    "/api/map": lambda q: code_map(q.get("mode", "overview")),
    "/api/timeline": lambda q: {"items": [{"kind": "prompt", "text": "Show the cart total with tax and shipping"},
                                          {"kind": "thinking", "text": "The total is computed in lib/cart.ts."},
                                          {"kind": "tool", "text": "Read cart.ts"}, {"kind": "tool", "text": "Edit CartSummary.tsx"}]},
}
PAGES = {"/": "index.html", "/activity": "activity.html"}


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        path, _, query = self.path.partition("?")
        q = dict(p.split("=", 1) for p in query.split("&") if "=" in p)
        if path in ROUTES:
            body, ctype = json.dumps(ROUTES[path](q)).encode(), "application/json"
        else:
            name = PAGES.get(path, path.lstrip("/"))
            target = os.path.join(WEB, name)
            if os.path.dirname(os.path.realpath(target)) != os.path.realpath(WEB) or not os.path.isfile(target):
                self.send_error(404)
                return
            body = open(target, "rb").read()
            ctype = {"css": "text/css", "js": "text/javascript", "html": "text/html"}[name.rsplit(".", 1)[1]]
        self.send_response(200)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        if self.path.startswith("/api/settings") and body:
            SETTINGS.update({k: v for k, v in json.loads(body).items() if k in SETTINGS and isinstance(v, bool)})
        self.do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 47821
    print(f"Pitwall demo on http://127.0.0.1:{port}/?t=demo")
    http.server.HTTPServer(("127.0.0.1", port), Handler).serve_forever()
