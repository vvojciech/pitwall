"use strict";
// Card order (tabs or activity) and card names (rename). Loads after app.js and uses its globals.

// The server sends cards in tab order. Activity order puts the agents that need you first.
const NEED = { waiting_permission: 0, waiting_input: 1, failed: 2, working: 3, done: 4, idle: 5 };
function ordered(list) {
  if (ui.order !== "activity") return list;
  return [...list].sort((a, b) => (NEED[a.state] ?? 9) - (NEED[b.state] ?? 9) || b.updated - a.updated);
}

function setOrder(order) {
  ui.order = order === "activity" ? "activity" : "tabs";
  try { localStorage.setItem("pitwall.order", ui.order); } catch { /* private mode: keep it for this view */ }
  document.querySelectorAll("#order button").forEach((b) => b.classList.toggle("on", b.dataset.order === ui.order));
  render();
}

// How full the agent's context window is, as a ring. Hover for the numbers.
function contextRing(s) {
  const c = s.context;
  if (!c || c.used == null) return "";
  const used = Math.max(0, Math.min(100, c.used));
  const level = used >= 90 ? "crit" : used >= 80 ? "warn" : "ok";
  const r = 7, length = 2 * Math.PI * r;
  const size = c.size >= 1e6 ? `${c.size / 1e6}M` : c.size ? `${Math.round(c.size / 1000)}k` : "";
  const tokens = c.tokens ? `, ${Math.round(c.tokens / 1000)}k tokens` : "";
  return `<span class="ring ${level}" title="Context ${used}% full${size ? ` of ${size}` : ""}${tokens}" aria-label="Context ${used}% full">
    <svg viewBox="0 0 18 18" aria-hidden="true"><circle class="track" cx="9" cy="9" r="${r}"/>
    <circle class="fill" cx="9" cy="9" r="${r}" stroke-dasharray="${(length * used / 100).toFixed(2)} ${length.toFixed(2)}" transform="rotate(-90 9 9)"/></svg></span>`;
}

// Background work Claude Code reported at its last stop: shells, sub-agents, monitors, wake-ups.
const BG_SHOWN = 3;
function backgroundList(s) {
  const tasks = s.background || [];
  const crons = s.crons || 0;
  if (!tasks.length && !crons) return "";
  const row = (type, text, status) => `<li><span class="bg-type">${esc(type)}</span>
    <span class="bg-desc">${esc(text)}</span>${status ? `<span class="bg-status">${esc(status)}</span>` : ""}</li>`;
  let rows = tasks.slice(0, BG_SHOWN).map((t) => row(t.type || "task", t.description || t.command || "", t.status)).join("");
  if (tasks.length > BG_SHOWN) rows += `<li class="bg-more">and ${tasks.length - BG_SHOWN} more</li>`;
  if (crons) rows += row("wake-up", `${crons} scheduled`, "");
  const all = tasks.map((t) => `${t.type}: ${t.description || t.command} (${t.status})`).join("\n");
  return `<ul class="bg" title="${esc(all)}">${rows}</ul>`;
}

// Your name for the card, else the iTerm2 tab's own name, else the project folder.
function cardName(s) {
  const project = base(s.cwd) || s.title;
  if (ui.renaming === s.sid) {
    return `<input class="rename-input" data-rename="${esc(s.sid)}" data-stop value="${esc(s.name || s.tab_name || "")}"
      placeholder="${esc(project)}" maxlength="60" aria-label="Name this agent" spellcheck="false">`;
  }
  const name = s.name || s.tab_name;
  const shown = name ? `${esc(name)}${name !== project ? `<small>${esc(project)}</small>` : ""}` : esc(project);
  return `<span class="project" title="Double-click to rename">${shown}</span>
    <button class="icon-btn small rename" data-act="rename" aria-label="Rename" title="Rename">${ICON.pencil}</button>`;
}

// Rename: double-click the name or use the pencil. Enter or leaving the field saves, Escape cancels.
function startRename(sid) {
  ui.renaming = sid;
  render();
  const input = document.querySelector("[data-rename]");
  if (input) { input.focus(); input.select(); }
}

async function finishRename(input, save) {
  const sid = input.dataset.rename;
  if (ui.renaming !== sid) return;
  ui.renaming = null;
  input.blur();
  if (save) {
    try { await api("/api/rename", { sid, name: input.value }); } catch (e) { toast(e.message); }
  }
  await poll();
}

$("cards").addEventListener("dblclick", (e) => {
  const name = e.target.closest(".project");
  const el = name && name.closest("[data-sid]");
  if (el) startRename(el.dataset.sid);
});
$("cards").addEventListener("keydown", (e) => {
  if (!e.target.dataset.rename) return;
  if (e.key === "Enter") finishRename(e.target, true);
  if (e.key === "Escape") finishRename(e.target, false);
});
$("cards").addEventListener("focusout", (e) => { if (e.target.dataset.rename) finishRename(e.target, true); });
$("order").addEventListener("click", (e) => { const b = e.target.closest("[data-order]"); if (b) setOrder(b.dataset.order); });
try { setOrder(localStorage.getItem("pitwall.order")); } catch { setOrder("tabs"); }

// Claude's AskUserQuestion menu, answered from the card. One single-choice question sends on click;
// otherwise the picks collect until Send. "Type something" and "Chat about this" stay in the tab.
function picksFor(s) {
  const key = JSON.stringify(s.questions.map((q) => q.question));
  ui.picks ||= {};
  if (ui.picks[s.sid]?.key !== key) ui.picks[s.sid] = { key, picks: s.questions.map(() => []) };
  return ui.picks[s.sid].picks;
}

const oneClick = (s) => s.questions.length === 1 && !s.questions[0].multi;

function questionPanel(s, busy) {
  const picks = picksFor(s);
  const blocks = s.questions.map((q, qi) => `<div class="q">
    ${q.header ? `<div class="q-head">${esc(q.header)}${q.multi ? '<span>Pick any</span>' : ""}</div>` : ""}
    <p>${esc(q.question)}</p>
    <div class="opts" role="${q.multi ? "group" : "radiogroup"}">${q.options.map((o, oi) => {
      const on = picks[qi].includes(oi);
      return `<button class="opt${on ? " on" : ""}" data-act="pick" data-q="${qi}" data-o="${oi}" aria-pressed="${on}" ${busy}>
        <b>${esc(o.label)}</b>${o.description ? `<small>${esc(o.description)}</small>` : ""}</button>`;
    }).join("")}</div></div>`).join("");
  const ready = picks.every((p) => p.length);
  const send = oneClick(s) ? "" : `<div class="row"><button class="btn primary" data-act="answer" ${ready && !busy ? "" : "disabled"}>
    ${ICON.check}Send ${s.questions.length > 1 ? "answers" : "answer"}</button></div>`;
  return `<div class="ask questions" data-stop>${blocks}${send}
    <div class="hint">To type your own answer, open the tab.</div></div>`;
}

// Returns true when the click should send the answers now.
function pick(s, button) {
  const picks = picksFor(s), qi = +button.dataset.q, oi = +button.dataset.o;
  const chosen = picks[qi];
  if (s.questions[qi].multi) {
    const at = chosen.indexOf(oi);
    if (at >= 0) chosen.splice(at, 1); else chosen.push(oi);
  } else {
    picks[qi] = [oi];
  }
  return oneClick(s);
}
