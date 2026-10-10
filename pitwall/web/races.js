"use strict";
// Agent races: the start form, the race cards, diff, apply and clean up. Uses app.js globals.

const FLAG = '<svg viewBox="0 0 24 24"><path d="M4 22V4"/><path d="M4 4h12l-2 4 2 4H4"/></svg>';

function raceForm() {
  const f = ui.raceForm;
  if (!f) return "";
  const projects = ui.raceProjects || [];
  if (!projects.length) {
    return `<section class="race-form panel"><p>Start an agent in a git project first. Races run in that project.</p>
      <div class="row"><button class="btn" data-race="form-close">Close</button></div></section>`;
  }
  if (!projects.includes(f.repo)) f.repo = projects[0];
  const count = (agent) => `<div class="seg">${[0, 1, 2].map((n) =>
    `<button class="${f[agent] === n ? "on" : ""}" data-race="count" data-agent="${agent}" data-value="${n}">${n}</button>`).join("")}</div>`;
  const total = f.claude + f.codex;
  return `<section class="race-form panel handoff">
    <label>Project</label><select data-race-repo>${projects.map((p) =>
      `<option value="${esc(p)}" ${p === f.repo ? "selected" : ""}>${esc(p.split("/").pop())}</option>`).join("")}</select>
    <label>Task</label><textarea data-race-task placeholder="What should each agent do?">${esc(f.task)}</textarea>
    <div class="counts"><div><label>Claude</label>${count("claude")}</div><div><label>Codex</label>${count("codex")}</div></div>
    <p class="hint-line">Each agent works in its own worktree from the current commit, in one new tab. Your files stay as they are until you apply a result.</p>
    <div class="row"><button class="btn primary" data-race="start" ${total < 2 || !f.task.trim() || ui.raceBusy ? "disabled" : ""}>${FLAG}Start ${total} agents</button>
    <button class="btn" data-race="form-close">Cancel</button></div></section>`;
}

function stateWord(state) {
  return { starting: "Starting", working: "Working", waiting_permission: "Needs permission", waiting_input: "Waiting",
    done: "Done", failed: "Failed", idle: "Idle", trust: "Needs folder trust" }[state] || state;
}

function raceCard(r) {
  const rows = r.entries.map((e) => {
    const st = e.stat;
    const size = !st ? "worktree removed" : st.files
      ? `<span class="add">+${st.added}</span> <span class="del">−${st.removed}</span> · ${st.files} file${st.files === 1 ? "" : "s"}`
      : "no changes yet";
    const open = ui.raceDiff && ui.raceDiff.id === r.id && ui.raceDiff.n === e.n;
    return `<div class="entry ${e.state}"><span class="dot"></span>
      <span class="ename">${AGENT[e.agent]} ${r.entries.filter((x) => x.agent === e.agent).length > 1 ? e.n + 1 : ""}</span>
      <span class="estate">${stateWord(e.state)}</span><span class="esize">${size}</span>
      <span class="row">${e.state === "trust" ? `<button class="btn ghost" data-race="show" data-id="${r.id}" data-n="${e.n}">Show</button>
        <button class="btn primary" data-race="trust" data-id="${r.id}" data-n="${e.n}">Trust</button>` : ""}
      ${st && st.files ? `<button class="btn ghost${open ? " on" : ""}" data-race="diff" data-id="${r.id}" data-n="${e.n}">Diff</button>` : ""}
      ${e.applied ? `<span class="applied">${ICON.check}Applied</span>` : st && st.files
        ? `<button class="btn" data-race="apply" data-id="${r.id}" data-n="${e.n}">Apply</button>` : ""}</span></div>
      ${open ? `<pre class="race-diff">${ui.raceDiff.text == null ? "Reading the diff…" : colourDiff(ui.raceDiff.text)}</pre>` : ""}`;
  }).join("");
  const clean = ui.raceClean === r.id
    ? `<div class="confirm">Close the race tab and delete its worktrees and branches?
        <div class="row"><button class="btn danger" data-race="clean-yes" data-id="${r.id}">Clean up</button>
        <button class="btn ghost" data-race="clean-no">Keep</button></div></div>`
    : `<button class="btn ghost" data-race="clean" data-id="${r.id}">Clean up</button>`;
  return `<div class="race"><div class="head">${FLAG}<span class="rtask">${esc(r.task)}</span></div>
    <div class="meta">${esc(r.project)} · ${r.entries.length} agents</div>${rows}<div class="race-foot">${clean}</div></div>`;
}

function colourDiff(text) {
  return esc(text).split("\n").map((l) => l.startsWith("+") && !l.startsWith("+++") ? `<span class="add">${l}</span>`
    : l.startsWith("-") && !l.startsWith("---") ? `<span class="del">${l}</span>`
    : l.startsWith("@@") ? `<span class="hunk">${l}</span>` : l).join("\n");
}

function racesSection() {
  const list = ui.races || [];
  return list.length ? `<section class="group"><h2>Races</h2>${list.map(raceCard).join("")}</section>` : "";
}

async function pollRaces() {
  try {
    const res = await api("/api/races");
    ui.races = res.races;
    ui.raceProjects = res.projects;
  } catch { ui.races = []; }
}

async function raceAct(button) {
  const kind = button.dataset.race;
  const id = button.dataset.id;
  const n = Number(button.dataset.n);
  try {
    if (kind === "form-close") ui.raceForm = null;
    else if (kind === "count") ui.raceForm[button.dataset.agent] = Number(button.dataset.value);
    else if (kind === "clean") ui.raceClean = id;
    else if (kind === "clean-no") ui.raceClean = null;
    else if (kind === "diff") {
      if (ui.raceDiff && ui.raceDiff.id === id && ui.raceDiff.n === n) ui.raceDiff = null;
      else {
        ui.raceDiff = { id, n, text: null };
        render();
        const res = await api(`/api/race/diff?id=${encodeURIComponent(id)}&n=${n}`);
        if (ui.raceDiff && ui.raceDiff.id === id) ui.raceDiff.text = res.diff;
      }
    } else {
      button.disabled = true;
      if (kind === "start") {
        const f = ui.raceForm;
        ui.raceBusy = true;
        const agents = [...Array(f.claude).fill("claude"), ...Array(f.codex).fill("codex")];
        await api("/api/race/start", { repo: f.repo, task: f.task, agents });
        ui.raceForm = null;
        toast(`${agents.length} agents started in a new tab.`);
      } else if (kind === "trust" || kind === "show") {
        await api(`/api/race/${kind}`, { id, n });
      } else if (kind === "apply") {
        await api("/api/race/apply", { id, n });
        toast("Applied to your project. Nothing is staged or committed.");
      } else if (kind === "clean-yes") {
        await api("/api/race/clean", { id });
        ui.raceClean = null;
        if (ui.raceDiff && ui.raceDiff.id === id) ui.raceDiff = null;
      }
      await pollRaces();
    }
  } catch (e) { toast(e.message); }
  ui.raceBusy = false;
  render();
}

function toggleRaceForm() {
  ui.raceForm = ui.raceForm ? null : { repo: "", task: "", claude: 1, codex: 1 };
  pollRaces().then(render);
  render();
}
