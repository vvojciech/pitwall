"use strict";
const params = new URLSearchParams(location.search);
const TOKEN = params.get("t") || "";
const MISSION = params.get("view") === "mission";
const $ = (id) => document.getElementById(id);
const ui = { undo: {}, pending: {}, data: null, offset: 0, html: "" };

const LABELS = {
  working: "Working", waiting_permission: "Needs permission", waiting_input: "Waiting for you",
  done: "Done", failed: "Failed", idle: "Idle",
};
const ICON = {
  check: '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  undo: '<svg viewBox="0 0 24 24"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>',
  redo: '<svg viewBox="0 0 24 24"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg>',
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const base = (p) => (p || "").replace(/\/+$/, "").split("/").pop() || p || "";

function since(ts) {
  const s = Math.max(0, Math.floor(Date.now() / 1000 + ui.offset - ts));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${String(s % 60).padStart(2, "0")}s`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

async function api(path, body) {
  const res = await fetch(path, {
    method: body ? "POST" : "GET",
    headers: { "X-Pitwall-Token": TOKEN, "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`);
  return data;
}

let toastTimer;
function toast(text) {
  const el = $("toast");
  el.textContent = text;
  el.classList.add("show");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove("show"), 4000);
}

function timerAttr(s) {
  if (s.state === "working" || s.state.startsWith("waiting")) return s.started ? `data-since="${s.started}"` : "";
  return s.finished ? `data-since="${s.finished}" data-suffix=" ago"` : "";
}

function undoPanel(s) {
  const u = ui.undo[s.sid];
  if (!u) return "";
  if (u.loading) return `<div class="undo" data-stop>Checking what changed…</div>`;
  if (!u.files.length) {
    return `<div class="undo" data-stop><p>Nothing changed since that prompt.</p>
      <div class="row"><button class="btn" data-act="undo-cancel">Close</button></div></div>`;
  }
  const shown = u.files.slice(0, 12).map(([action, path]) =>
    `<li><span>${action === "delete" ? "remove" : "restore"}</span><span>${esc(path)}</span></li>`).join("");
  const more = u.files.length > 12 ? `<li><span></span><span>and ${u.files.length - 12} more</span></li>` : "";
  return `<div class="undo" data-stop>
    <p>Put ${u.files.length} file${u.files.length === 1 ? "" : "s"} back to before “${esc(u.task || "the last prompt")}”?</p>
    <ul>${shown}${more}</ul>
    <div class="row"><button class="btn primary" data-act="undo-go" ${ui.pending[s.sid] ? "disabled" : ""}>Restore</button>
    <button class="btn" data-act="undo-cancel">Cancel</button></div></div>`;
}

function card(s) {
  const busy = ui.pending[s.sid] ? "disabled" : "";
  const waiting = s.state === "waiting_permission";
  const task = s.task ? `<div class="task">${esc(s.task)}</div>` : `<div class="task empty">No prompt yet</div>`;
  const action = s.action && s.state !== "done" ? `<div class="action">${esc(s.action)}</div>` : "";
  const ask = waiting ? `<div class="ask" data-stop>
      ${s.permission ? `<div class="what">${esc(s.permission)}</div>` : ""}
      <div class="row"><button class="btn primary" data-act="allow" ${busy}>${ICON.check}Allow</button>
      <button class="btn" data-act="deny" ${busy}>${ICON.x}Deny</button></div></div>` : "";
  const settled = !["working", "waiting_permission"].includes(s.state);
  const tools = settled && !ui.undo[s.sid] && (s.can_undo || s.can_redo) ? `<div class="footer" data-stop>
      ${s.can_redo ? `<button class="btn ghost" data-act="redo" ${busy}>${ICON.redo}Redo</button>` : ""}
      ${s.can_undo ? `<button class="btn ghost" data-act="undo" ${busy}>${ICON.undo}Undo turn</button>` : ""}</div>` : "";
  const screen = MISSION ? `<div class="screen">${esc(s.screen || "")}</div>` : "";
  return `<article class="card ${s.state}${s.unseen ? " unseen" : ""}${s.focused ? " focused" : ""}" data-sid="${esc(s.sid)}" title="Go to this tab">
    <div class="head"><span class="dot"></span><span class="project">${esc(base(s.cwd) || s.title)}</span>
      <span class="timer" ${timerAttr(s)}></span></div>
    <div class="meta"><span class="agent ${esc(s.agent)}">${s.agent === "claude" ? "Claude" : "Codex"}</span>·
      <span class="state-label">${LABELS[s.state] || esc(s.state)}</span></div>
    ${task}${action}${s.state === "failed" && s.error ? `<div class="error">${esc(s.error)}</div>` : ""}
    ${ask}${undoPanel(s)}${tools}${screen}</article>`;
}

function summary(list) {
  const n = (st) => list.filter((s) => st.includes(s.state)).length;
  const parts = [];
  const waiting = n(["waiting_permission", "waiting_input"]);
  if (waiting) parts.push(`<b>${waiting} waiting</b>`);
  if (n(["working"])) parts.push(`${n(["working"])} working`);
  if (MISSION && n(["done"])) parts.push(`${n(["done"])} done`);
  return parts.join(" · ") || (list.length ? "All quiet" : "");
}

function render() {
  const list = ui.data ? ui.data.sessions : [];
  let html;
  if (!ui.data) {
    html = `<div class="empty-state"><strong>Pitwall is not running</strong>Run <code>pitwall doctor</code> in a terminal.</div>`;
  } else if (!list.length) {
    html = `<div class="empty-state"><strong>No agents yet</strong>Start Claude Code or Codex in any iTerm2 tab and it shows up here.</div>`;
  } else {
    html = list.map(card).join("");
  }
  $("summary").innerHTML = summary(list);
  document.title = list.some((s) => s.state.startsWith("waiting")) ? "Pitwall (needs you)" : "Pitwall";
  if (html !== ui.html) {
    $("cards").innerHTML = html;
    ui.html = html;
  }
  tick();
}

function tick() {
  document.querySelectorAll("[data-since]").forEach((el) => {
    el.textContent = since(Number(el.dataset.since)) + (el.dataset.suffix || "");
  });
}

async function poll() {
  try {
    const data = await api(`/api/state${MISSION ? "?screen=1" : ""}`);
    ui.offset = data.now - Date.now() / 1000;
    ui.data = data;
  } catch {
    ui.data = null;
  }
  render();
}

async function act(sid, name) {
  if (name === "undo-cancel") { delete ui.undo[sid]; return render(); }
  ui.pending[sid] = true;
  render();
  try {
    if (name === "allow" || name === "deny") {
      await api("/api/respond", { sid, allow: name === "allow" });
    } else if (name === "undo") {
      ui.undo[sid] = { loading: true };
      render();
      const res = await api(`/api/undo?sid=${encodeURIComponent(sid)}`);
      ui.undo[sid] = { files: res.files, task: res.task };
    } else if (name === "undo-go") {
      await api("/api/undo", { sid });
      delete ui.undo[sid];
      toast("Turn undone. Your files are back to before that prompt.");
    } else if (name === "redo") {
      await api("/api/redo", { sid });
      toast("Redone. The agent's changes are back.");
    }
  } catch (e) {
    if (name === "undo") delete ui.undo[sid];
    toast(e.message);
  } finally {
    delete ui.pending[sid];
    await poll();
  }
}

$("cards").addEventListener("click", (e) => {
  const el = e.target.closest("[data-sid]");
  if (!el) return;
  const button = e.target.closest("[data-act]");
  if (button) return act(el.dataset.sid, button.dataset.act);
  if (e.target.closest("[data-stop]")) return;
  api("/api/focus", { sid: el.dataset.sid }).catch((err) => toast(err.message));
});
$("mission").addEventListener("click", () => api("/api/mission", {}).catch((err) => toast(err.message)));

if (MISSION) document.body.classList.add("mission");
poll();
setInterval(() => { if (!document.hidden) poll(); }, MISSION ? 1500 : 1000);
setInterval(tick, 1000);
