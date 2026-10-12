"use strict";
// Timeline, hand-off, failed commands and ports. app.js calls these; they share its `ui`, `api` and `esc`.

const MORE_ICON = {
  list: '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  open: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  stop: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>',
  loop: '<svg viewBox="0 0 24 24"><path d="M17 2l4 4-4 4"/><path d="M3 11V9a3 3 0 0 1 3-3h15M7 22l-4-4 4-4"/><path d="M21 13v2a3 3 0 0 1-3 3H3"/></svg>',
};
const AGENT = { claude: "Claude", codex: "Codex" };

function loopStartPanel(s) {
  const l = ui.loopStart[s.sid];
  if (!l) return "";
  const seg = (name, options, value) => `<div class="seg">${options.map(([v, label]) =>
    `<button class="${String(v) === String(value) ? "on" : ""}" data-act="loop-${name}" data-value="${v}">${label}</button>`).join("")}</div>`;
  return `<div class="panel handoff" data-stop>
    <label>Reviewer</label>${seg("reviewer", [["codex", "Codex"], ["claude", "Claude"]], l.reviewer)}
    <label>Rounds at most</label>${seg("rounds", [[2, "2"], [3, "3"], [5, "5"]], l.rounds)}
    <label class="check"><input type="checkbox" data-act="loop-auto" ${l.auto ? "checked" : ""}> Send each message automatically</label>
    <p class="hint-line">The reviewer opens in a new split and reviews this agent's changes. Its findings go back to this agent until it answers APPROVED. ${l.auto ? "" : "You press Send for each message."}</p>
    <div class="row"><button class="btn primary" data-act="loop-go" ${ui.pending[s.sid] ? "disabled" : ""}>${MORE_ICON.loop}Start</button>
    <button class="btn" data-act="loop-cancel">Cancel</button></div></div>`;
}

function loopStrip(s) {
  if (s.reviews) return `<div class="loop-strip quiet">${MORE_ICON.loop}<span>Reviewer for <b>${esc(s.reviews)}</b></span></div>`;
  const l = s.loop;
  if (!l) return "";
  const who = AGENT[l.reviewer_agent] || l.reviewer_agent;
  const round = `round ${l.round} of ${l.max}`;
  const done = { approved: ["ok", `Approved by ${who} in ${round}`], limit: ["warn", `No approval after ${l.max} rounds`],
    stopped: ["quiet", "Review loop stopped"] }[l.phase];
  if (done) {
    return `<div class="loop-strip ${done[0]}" data-stop>${MORE_ICON.loop}<span>${done[1]}</span>
      <button class="btn ghost" data-act="loop-close">Close</button></div>`;
  }
  const p = l.pending;
  const status = p ? (p.to === "writer" ? `${who} asks for changes · ${round}` : `Fixes ready for ${who} · ${round}`)
    : (l.phase === "reviewing" ? `${who} is reviewing · ${round}` : `Fixing the review · ${round}`);
  const send = p ? `<div class="row"><button class="btn primary" data-act="loop-send" ${ui.pending[s.sid] ? "disabled" : ""}>${MORE_ICON.send}Send to ${p.to === "writer" ? "this agent" : who}</button></div>
      <details><summary>Show the message</summary><pre>${esc(p.text)}</pre></details>` : "";
  return `<div class="loop-strip ${p ? "ready" : "live"}" data-stop>${MORE_ICON.loop}<span>${status}</span>
    <button class="btn ghost" data-act="loop-stop">Stop</button>${send}</div>`;
}
const KIND = { prompt: "You", text: "Says", thinking: "Thinks", tool: "Runs", agent: "Sub-agent" };
const MODES = [["continue", "Continue"], ["review", "Review"], ["second", "Opinion"]];

function cardTools(s, busy) {
  const settled = !["working", "waiting_permission"].includes(s.state);
  const open = ui.timeline[s.sid] ? " on" : "";
  // A card found by the scan has no transcript or task until the agent fires its first hook.
  const known = Boolean(s.agent_session);
  if (!known && !s.can_undo && !s.can_redo) return "";
  return `<div class="footer" data-stop>
    ${known ? `<button class="btn ghost${open}" data-act="timeline">${MORE_ICON.list}Timeline</button>
    <button class="btn ghost${ui.handoff[s.sid] ? " on" : ""}" data-act="handoff">${MORE_ICON.send}Hand off</button>` : ""}
    ${known && !s.loop && !s.reviews ? `<button class="btn ghost${ui.loopStart[s.sid] ? " on" : ""}" data-act="loop">${MORE_ICON.loop}Review loop</button>` : ""}
    ${settled && s.can_redo ? `<button class="btn ghost" data-act="redo" ${busy}>${ICON.redo}Redo</button>` : ""}
    ${settled && s.can_undo ? `<button class="btn ghost" data-act="undo" ${busy}>${ICON.undo}Undo</button>` : ""}</div>`;
}

function timelinePanel(s) {
  const t = ui.timeline[s.sid];
  if (!t) return "";
  if (!t.items) return `<div class="panel" data-stop>Reading the transcript…</div>`;
  if (!t.items.length) return `<div class="panel" data-stop>No transcript yet. It appears after the agent's first hook event.</div>`;
  const rows = t.items.map((i) => `<li class="k-${i.kind}"><span>${KIND[i.kind] || i.kind}</span><span>${esc(i.text)}</span></li>`).join("");
  return `<div class="panel timeline" data-stop><ol>${rows}</ol></div>`;
}

// The agents a hand-off can open: the installed ones (an older service sends no list: offer both).
function handoffTargets() {
  const installed = ui.data?.agents;
  return [["claude", "Claude"], ["codex", "Codex"]].filter(([a]) => !installed?.length || installed.includes(a));
}

function handoffPanel(s) {
  const h = ui.handoff[s.sid];
  if (!h) return "";
  const seg = (name, options, value) => `<div class="seg">${options.map(([v, label]) =>
    `<button class="${v === value ? "on" : ""}" data-act="handoff-${name}" data-value="${v}">${label}</button>`).join("")}</div>`;
  return `<div class="panel handoff" data-stop>
    <label>Send to</label>${seg("to", handoffTargets(), h.to)}
    <label>Ask it to</label>${seg("mode", MODES, h.mode)}
    <textarea data-handoff="${esc(s.sid)}" spellcheck="false" ${h.text == null ? "disabled" : ""}>${esc(h.text ?? "Writing the hand-off…")}</textarea>
    <p class="hint-line">Opens in a new split beside this agent.</p>
    <div class="row"><button class="btn primary" data-act="handoff-go" ${h.text == null || ui.pending[s.sid] ? "disabled" : ""}>${MORE_ICON.send}Send</button>
    <button class="btn" data-act="handoff-cancel">Cancel</button></div></div>`;
}

function failuresSection(list) {
  if (!list || !list.length) return "";
  const rows = list.map((f) => {
    const actions = f.agent_sid
      ? `<button class="btn" data-fail="send" data-id="${f.id}">${MORE_ICON.send}Send to ${f.agent === "codex" ? "Codex" : "Claude"}</button>`
      : `<button class="btn" data-fail="fix" data-to="claude" data-id="${f.id}">Fix with Claude</button>
         <button class="btn" data-fail="fix" data-to="codex" data-id="${f.id}">Codex</button>`;
    return `<div class="failure"><div class="head"><span class="fcmd">${esc(f.command)}</span>
        <button class="icon-btn small" data-fail="dismiss" data-id="${f.id}" aria-label="Dismiss">${ICON.x}</button></div>
      <div class="meta">exit ${f.status} · ${esc(f.project || f.cwd)}</div>
      <pre>${esc(f.output.split("\n").slice(-4).join("\n"))}</pre>${busyPort(f)}<div class="row">${actions}</div></div>`;
  }).join("");
  return `<section class="group"><h2>Failed commands</h2>${rows}</section>`;
}

function busyPort(f) {
  const b = f.busy;
  if (!b) return "";
  const who = `${esc(b.command)}${b.project ? ` in ${esc(b.project)}` : ""}`;
  const action = ui.freeing === f.id
    ? `<div class="row"><button class="btn danger" data-fail="free-port" data-id="${f.id}">${MORE_ICON.stop}Stop ${esc(b.command)}</button>
       <button class="btn ghost" data-fail="free-cancel" data-id="${f.id}">Keep it</button></div>`
    : `<button class="btn danger" data-fail="free-ask" data-id="${f.id}">${MORE_ICON.stop}Stop it</button>`;
  return `<div class="busy"><span>Port <b>${b.port}</b> is held by ${who} (pid ${b.pid}).</span>${action}</div>`;
}

function portsSection() {
  const list = ui.ports;
  if (!list || !list.length) return "";
  const rows = list.map((p) => ui.stopping === p.pid
    ? `<div class="port"><span class="pnum">:${p.port}</span><span class="pname">Stop ${esc(p.command)}?</span>
        <button class="btn" data-port="stop-yes" data-pid="${p.pid}">Stop</button><button class="btn ghost" data-port="stop-no">Keep</button></div>`
    : `<div class="port"><span class="pnum">:${p.port}</span><span class="pname">${esc(p.command)} · ${esc(p.project)}</span>
        <button class="icon-btn small" data-port="open" data-portnum="${p.port}" title="Open in the browser">${MORE_ICON.open}</button>
        <button class="icon-btn small" data-port="stop" data-pid="${p.pid}" title="Stop">${MORE_ICON.stop}</button></div>`).join("");
  return `<section class="group"><h2>Ports</h2>${rows}</section>`;
}

async function loadTimeline(sid) {
  const res = await api(`/api/timeline?sid=${encodeURIComponent(sid)}`);
  if (ui.timeline[sid]) ui.timeline[sid].items = res.items;
}

async function loadHandoff(sid) {
  const h = ui.handoff[sid];
  h.text = null;
  render();
  const res = await api(`/api/handoff?sid=${encodeURIComponent(sid)}&mode=${h.mode}`);
  if (ui.handoff[sid] === h) h.text = res.text;
}

// The footer panels share one slot on the card: opening one closes the others.
function openPanel(sid, panel, value) {
  for (const p of ["timeline", "handoff", "loopStart"]) delete ui[p][sid];
  ui[panel][sid] = value;
}

// Returns true when the action was one of these features.
async function featureAct(sid, name, button) {
  if (name === "timeline") {
    if (ui.timeline[sid]) delete ui.timeline[sid];
    else { openPanel(sid, "timeline", {}); render(); await loadTimeline(sid); }
  } else if (name === "handoff") {
    if (ui.handoff[sid]) delete ui.handoff[sid];
    else { openPanel(sid, "handoff", { to: handoffTargets().some(([a]) => a === "codex") ? "codex" : "claude", mode: "continue" }); await loadHandoff(sid); }
  } else if (name === "handoff-to") {
    ui.handoff[sid].to = button.dataset.value;
  } else if (name === "handoff-mode") {
    ui.handoff[sid].mode = button.dataset.value;
    await loadHandoff(sid);
  } else if (name === "handoff-cancel") {
    delete ui.handoff[sid];
  } else if (name === "loop") {
    if (ui.loopStart[sid]) delete ui.loopStart[sid];
    else openPanel(sid, "loopStart", { reviewer: "codex", rounds: 3, auto: false });
  } else if (name === "loop-reviewer" || name === "loop-rounds") {
    ui.loopStart[sid][name.slice(5)] = name === "loop-rounds" ? Number(button.dataset.value) : button.dataset.value;
  } else if (name === "loop-auto") {
    ui.loopStart[sid].auto = button.checked;
  } else if (name === "loop-cancel") {
    delete ui.loopStart[sid];
  } else if (name === "loop-go") {
    const l = ui.loopStart[sid];
    await api("/api/loop/start", { sid, reviewer: l.reviewer, rounds: l.rounds, auto: l.auto });
    delete ui.loopStart[sid];
    toast(`${AGENT[l.reviewer]} is starting in a new split to review this work.`);
  } else if (["loop-send", "loop-stop", "loop-close"].includes(name)) {
    await api(`/api/loop/${name.slice(5)}`, { sid });
  } else if (name === "sched-stop") {
    await api("/api/schedule/stop", { sid, id: button.dataset.id });
    toast("Asked Claude to cancel it. The row goes when Claude confirms.");
  } else if (name === "handoff-go") {
    const h = ui.handoff[sid];
    await api("/api/handoff", { sid, to: h.to, text: h.text });
    delete ui.handoff[sid];
    toast(`Sent to ${h.to === "codex" ? "Codex" : "Claude"} in a new split.`);
  } else {
    return false;
  }
  return true;
}

async function failureAct(button) {
  const id = Number(button.dataset.id);
  if (button.dataset.fail === "free-ask" || button.dataset.fail === "free-cancel") {
    ui.freeing = button.dataset.fail === "free-ask" ? id : null;
    return render();
  }
  ui.freeing = null;
  button.disabled = true;
  try {
    const kind = button.dataset.fail;
    await api(`/api/failures/${kind}`, { id, to: button.dataset.to });
    if (kind === "free-port") toast("Stopped. Run your command again.");
    else if (kind !== "dismiss") toast("Sent. The agent has the command and its output.");
  } catch (e) { toast(e.message); }
  await poll();
}

async function portAct(button) {
  const kind = button.dataset.port;
  if (kind === "stop") ui.stopping = Number(button.dataset.pid);
  else if (kind === "stop-no") ui.stopping = null;
  else {
    button.disabled = true;
    try {
      if (kind === "open") await api("/api/ports/open", { port: Number(button.dataset.portnum) });
      if (kind === "stop-yes") { await api("/api/ports/stop", { pid: Number(button.dataset.pid) }); ui.stopping = null; }
    } catch (e) { toast(e.message); }
    await pollPorts();
  }
  render();
}

async function pollPorts() {
  try { ui.ports = (await api("/api/ports")).ports; } catch { ui.ports = []; }
}

async function pollTimelines() {
  await Promise.all(Object.keys(ui.timeline).map((sid) => loadTimeline(sid).catch(() => {})));
}

// The Update button in the top bar. It shows when GitHub has a newer Pitwall; a click runs `pitwall update`,
// which restarts the service, and iTerm2 then reloads the panel at the new address.
const UPDATE_ICON = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v11"/><path d="m7 10 5 5 5-5"/><path d="M5 20h14"/></svg>';
function updateButton() {
  const b = $("update"), u = ui.data && ui.data.update;
  if (ui.updating) {
    b.hidden = false; b.disabled = true; b.innerHTML = "Updating…";
    return;
  }
  b.hidden = !u; b.disabled = false; b.innerHTML = `${UPDATE_ICON}Update`;
  if (!u) return;
  const what = u.latest && u.latest !== `v${ui.data.version}` ? `Pitwall ${u.latest} is out` : "A newer Pitwall is out";
  b.title = `${what} (${u.behind} change${u.behind === 1 ? "" : "s"}). Click to update; the panel restarts.`;
}

async function startUpdate() {
  ui.updating = Date.now();
  updateButton();
  try {
    await api("/api/update", {});
  } catch (err) {
    ui.updating = null;
    toast(err.message);
    updateButton();
  }
}

// Called on each answer from the service: an update that is still not done after a minute failed.
function updateTimedOut() {
  if (!ui.updating || Date.now() - ui.updating < 60000) return;
  ui.updating = null;
  toast("The update did not finish. Run pitwall update in a terminal, or read ~/.pitwall/update.log.");
}
