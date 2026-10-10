"use strict";
// Timeline, hand-off, failed commands and ports. app.js calls these; they share its `ui`, `api` and `esc`.

const MORE_ICON = {
  list: '<svg viewBox="0 0 24 24"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>',
  send: '<svg viewBox="0 0 24 24"><path d="M5 12h14M13 6l6 6-6 6"/></svg>',
  open: '<svg viewBox="0 0 24 24"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
  stop: '<svg viewBox="0 0 24 24"><rect x="6" y="6" width="12" height="12" rx="1.5"/></svg>',
};
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

function handoffPanel(s) {
  const h = ui.handoff[s.sid];
  if (!h) return "";
  const seg = (name, options, value) => `<div class="seg">${options.map(([v, label]) =>
    `<button class="${v === value ? "on" : ""}" data-act="handoff-${name}" data-value="${v}">${label}</button>`).join("")}</div>`;
  return `<div class="panel handoff" data-stop>
    <label>Send to</label>${seg("to", [["claude", "Claude"], ["codex", "Codex"]], h.to)}
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
      <pre>${esc(f.output.split("\n").slice(-4).join("\n"))}</pre><div class="row">${actions}</div></div>`;
  }).join("");
  return `<section class="group"><h2>Failed commands</h2>${rows}</section>`;
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

// Returns true when the action was one of these features.
async function featureAct(sid, name, button) {
  if (name === "timeline") {
    if (ui.timeline[sid]) delete ui.timeline[sid];
    else { ui.timeline[sid] = {}; render(); await loadTimeline(sid); }
  } else if (name === "handoff") {
    if (ui.handoff[sid]) delete ui.handoff[sid];
    else { ui.handoff[sid] = { to: "codex", mode: "continue" }; await loadHandoff(sid); }
  } else if (name === "handoff-to") {
    ui.handoff[sid].to = button.dataset.value;
  } else if (name === "handoff-mode") {
    ui.handoff[sid].mode = button.dataset.value;
    await loadHandoff(sid);
  } else if (name === "handoff-cancel") {
    delete ui.handoff[sid];
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
  button.disabled = true;
  try {
    await api(`/api/failures/${button.dataset.fail}`, { id, to: button.dataset.to });
    if (button.dataset.fail !== "dismiss") toast("Sent. The agent has the command and its output.");
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
