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
