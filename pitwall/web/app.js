"use strict";
const params = new URLSearchParams(location.search);
const TOKEN = params.get("t") || "";
const $ = (id) => document.getElementById(id);
const ui = { undo: {}, pending: {}, data: null, offset: 0, html: "", timeline: {}, handoff: {}, loopStart: {}, map: { sid: null, mode: "turn", data: null }, ports: [], stopping: null };

const LABELS = {
  working: "Working", waiting_permission: "Needs permission", waiting_input: "Waiting for you",
  done: "Done", failed: "Failed", idle: "Idle",
};
const ICON = {
  check: '<svg viewBox="0 0 24 24"><path d="M20 6 9 17l-5-5"/></svg>',
  pencil: '<svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="m13.5 6.5 4 4"/></svg>',
  x: '<svg viewBox="0 0 24 24"><path d="M18 6 6 18M6 6l12 12"/></svg>',
  undo: '<svg viewBox="0 0 24 24"><path d="M9 14 4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/></svg>',
  redo: '<svg viewBox="0 0 24 24"><path d="m15 14 5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/></svg>',
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
// "shop", or "shop › feature" for a worktree under .claude/worktrees (as ports.project_name does).
function base(p) {
  const [repo, rest] = (p || "").replace(/\/+$/, "").split("/.claude/worktrees/");
  const name = repo.split("/").pop() || repo;
  return rest ? `${name} › ${rest.split("/")[0]}` : name;
}

// The prompt without image placeholders, else the title Claude gave the tab ("✳ Fix login (claude)").
function taskText(s) {
  const prompt = (s.task || "").replace(/\[Image #\d+\]/g, "").trim();
  if (prompt) return prompt;
  const title = (s.title || "").replace(/^[^\p{L}\p{N}]+/u, "").replace(/\s*\([^)]*\)\s*$/, "").trim();
  return ["Chat", "Claude Code", "Codex"].includes(title) ? "" : title;
}

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
  const text = taskText(s);
  const task = text ? `<div class="task">${esc(text)}</div>` : `<div class="task empty">No task yet</div>`;
  const action = s.action && s.state !== "done" && !s.questions ? `<div class="action">${esc(s.action)}</div>` : "";
  const ask = s.questions ? questionPanel(s, busy) : waiting ? `<div class="ask" data-stop>
      ${s.permission ? `<div class="what">${esc(s.permission)}</div>` : ""}
      <div class="row"><button class="btn primary" data-act="allow" ${busy}>${ICON.check}Allow</button>
      <button class="btn" data-act="deny" ${busy}>${ICON.x}Deny</button></div></div>` : "";
  const tools = ui.undo[s.sid] ? "" : cardTools(s, busy);
  return `<article class="card ${s.state}${s.unseen ? " unseen" : ""}${s.focused ? " focused" : ""}" data-sid="${esc(s.sid)}" title="Go to this tab">
    <div class="head"><span class="dot"></span>${cardName(s)}
      <span class="timer" ${timerAttr(s)}></span>${contextRing(s)}</div>
    <div class="meta"><span class="agent ${esc(s.agent)}">${s.agent === "claude" ? "Claude" : "Codex"}</span>·
      <span class="state-label">${s.questions ? "Asks you" : LABELS[s.state] || esc(s.state)}</span></div>
    ${task}${action}${backgroundList(s)}${s.state === "failed" && s.error ? `<div class="error">${esc(s.error)}</div>` : ""}
    ${ask}${loopStrip(s)}${undoPanel(s)}${tools}${loopStartPanel(s)}${timelinePanel(s)}${handoffPanel(s)}</article>`;
}

function summary(list) {
  const n = (st) => list.filter((s) => st.includes(s.state)).length;
  const parts = [];
  const waiting = n(["waiting_permission", "waiting_input"]);
  if (waiting) parts.push(`<b>${waiting} waiting</b>`);
  if (n(["working"])) parts.push(`${n(["working"])} working`);
  const background = list.reduce((sum, s) => sum + (s.background || []).length, 0);
  const jobs = list.flatMap((s) => s.schedules || []);
  const next = Math.min(...jobs.filter((j) => j.next && !j.stopping).map((j) => j.next));
  const scheduled = jobs.length ? `${jobs.length} scheduled${isFinite(next) ? ` · next <span data-until="${next}"></span>` : ""}` : "";
  const counts = [background && `${background} in background`, scheduled].filter(Boolean).join(" · ");
  if ($("bgcount").dataset.html !== counts) {
    $("bgcount").innerHTML = counts;
    $("bgcount").dataset.html = counts;
    $("bgcount").title = [background && `${background} background tasks`, jobs.length && `${jobs.length} scheduled prompts`]
      .filter(Boolean).join(", ") + " across all agents";
  }
  return parts.join(" · ") || (list.length ? "All quiet" : "");
}

function render() {
  const list = ui.data ? ui.data.sessions : [];
  let html;
  if (!ui.data) {
    html = ui.updating
      ? `<div class="empty-state"><strong>Updating Pitwall</strong>The panel comes back in a few seconds.</div>`
      : `<div class="empty-state"><strong>Pitwall is not running</strong>Run <code>pitwall doctor</code> in a terminal.</div>`;
  } else if (!list.length) {
    html = `<div class="empty-state"><strong>No agents yet</strong>Start Claude Code or Codex in any iTerm2 tab and it shows up here.</div>`;
  } else {
    html = ordered(list).map(card).join("");
  }
  if (ui.data) html = raceForm() + racesSection() + failuresSection(ui.data.failures) + html + mapSection(list) + portsSection();
  const bar = usageBar();
  if (bar !== ui.usageHtml) { $("usage").innerHTML = bar; ui.usageHtml = bar; }
  $("summary").innerHTML = summary(list);
  updateButton();
  document.title = list.some((s) => s.state.startsWith("waiting")) ? "Pitwall (needs you)" : "Pitwall";
  // Rebuilding the list would drop the caret in the hand-off text, so wait while it has focus.
  const typing = document.activeElement && ["TEXTAREA", "INPUT"].includes(document.activeElement.tagName);
  if (html !== ui.html && !typing) {
    $("cards").innerHTML = html;
    ui.html = html;
    document.querySelectorAll(".timeline ol").forEach((ol) => { ol.scrollTop = ol.scrollHeight; });
  }
  tick();
}

function tick() {
  document.querySelectorAll("[data-since]").forEach((el) => {
    el.textContent = since(Number(el.dataset.since)) + (el.dataset.suffix || "");
  });
  document.querySelectorAll("[data-until]").forEach((el) => {
    const text = until(Number(el.dataset.until));
    el.textContent = (el.dataset.prefix || "") + text;
    el.classList.toggle("due", text === "due");
  });
}

async function poll() {
  try {
    const data = await api("/api/state");
    ui.offset = data.now - Date.now() / 1000;
    ui.data = data;
    updateTimedOut();
  } catch {
    ui.data = null;
  }
  render();
}

async function act(sid, name) {
  if (name === "undo-cancel") { delete ui.undo[sid]; return render(); }
  if (name === "rename") return startRename(sid);
  const s = ui.data?.sessions.find((x) => x.sid === sid);
  if (name === "pick" && !(s?.questions && pick(s, ui.button))) return render();
  ui.pending[sid] = true;
  render();
  try {
    if (await featureAct(sid, name, ui.button)) {
      // handled in features.js
    } else if (name === "pick" || name === "answer") {
      await api("/api/answer", { sid, picks: picksFor(s) });
      delete ui.picks[sid];
    } else if (name === "allow" || name === "deny") {
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
  const fail = e.target.closest("[data-fail]");
  if (fail) return failureAct(fail);
  const mapMode = e.target.closest("[data-map-mode]");
  if (mapMode) return setMapMode(mapMode.dataset.mapMode);
  const port = e.target.closest("[data-port]");
  if (port) return portAct(port);
  const raceButton = e.target.closest("[data-race]");
  if (raceButton) return raceAct(raceButton);
  const el = e.target.closest("[data-sid]");
  if (!el) return;
  const button = e.target.closest("[data-act]");
  if (button) {
    ui.button = button;
    return act(el.dataset.sid, button.dataset.act);
  }
  if (e.target.closest("[data-stop]")) return;
  api("/api/focus", { sid: el.dataset.sid }).catch((err) => toast(err.message));
});
$("cards").addEventListener("input", (e) => {
  const sid = e.target.dataset.handoff;
  if (sid && ui.handoff[sid]) ui.handoff[sid].text = e.target.value;
  if (ui.raceForm && "raceTask" in e.target.dataset) {
    ui.raceForm.task = e.target.value;
    const start = document.querySelector('[data-race="start"]');
    if (start) start.disabled = ui.raceForm.claude + ui.raceForm.codex < 2 || !e.target.value.trim();
  }
});
$("cards").addEventListener("change", (e) => {
  if (ui.raceForm && "raceRepo" in e.target.dataset) ui.raceForm.repo = e.target.value;
});
$("race").addEventListener("click", toggleRaceForm);
$("update").addEventListener("click", startUpdate);
$("usage").addEventListener("click", (e) => {
  if (e.target.closest("[data-usage]")) api("/api/open", {}).catch((err) => toast(err.message));
});

poll();
setInterval(() => { if (!document.hidden) poll(); }, 1000);
setInterval(tick, 1000);
Promise.all([pollPorts(), pollRaces(), pollUsage()]).then(render);
setInterval(() => { if (!document.hidden) pollUsage(); }, 60000);
setInterval(() => { if (!document.hidden) pollPorts(); }, 5000);
setInterval(() => { if (!document.hidden) pollRaces(); }, 3000);
setInterval(() => { if (!document.hidden) { pollTimelines(); pollMaps(); } }, 2000);
