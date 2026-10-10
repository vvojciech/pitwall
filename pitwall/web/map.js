"use strict";
// The code map panel on a card: folders as a radial star map, touched files lit, blast radius dashed.

// Four hues that pass the all-pairs colour check on the map's dark surface; the rest is "Other".
const MAP_GROUPS = [["frontend", "Frontend", ["frontend", "assets"]], ["backend", "Backend & data", ["backend", "database"]],
  ["tests", "Tests", ["tests"]], ["config", "Config", ["config"]], ["other", "Other", ["code", "docs"]]];
const groupOf = (cat) => (MAP_GROUPS.find(([, , cats]) => cats.includes(cat)) || ["other"])[0];
const VERB = { edit: "Editing", read: "Reading" };
const DEP_LABELS = 4;  // above this many dependents, a chip counts them and their labels stay off
const depCount = (d) => d.nodes.filter((n) => n.dependent).length;

// The map follows the agent in the active iTerm2 pane. With no agent there, it keeps the last one.
function mapAgent(list) {
  const focused = list.find((s) => s.focused && s.cwd);
  if (focused) return focused;
  return list.find((s) => s.sid === ui.map.sid && s.cwd) || list.find((s) => s.cwd) || null;
}

function mapSection(list) {
  const s = mapAgent(list);
  if (!s) return "";
  if (ui.map.sid !== s.sid) {  // the active tab changed: show the new agent's map at once
    ui.map.sid = s.sid;
    ui.map.data = null;
    loadMap().then(render).catch(() => {});
  }
  const m = ui.map;
  const modes = [["turn", "This turn"], ["uncommitted", "Uncommitted"]].map(([v, l]) =>
    `<button class="${m.mode === v ? "on" : ""}" data-map-mode="${v}">${l}</button>`).join("");
  let body;
  if (!m.data) body = `<p class="map-note">Reading the changes…</p>`;
  else if (m.data.error) body = `<p class="map-note">${esc(m.data.error)}</p>`;
  else if (m.data.nodes.length < 2) {
    body = `<p class="map-note">${m.mode === "turn" ? "Nothing read or changed in this turn yet." : "No uncommitted changes."}</p>`;
  }
  else body = mapChips(m.data) + mapSvg(m.data, s) + mapLegend(m.data);
  const who = esc(s.name || s.tab_name || base(s.cwd));
  return `<section class="group"><h2 class="split">Map · ${who}<span class="map-follow">${s.focused ? "active tab" : "last active"}</span></h2>
    <div class="map-panel">${body}<div class="map-foot"><div class="seg">${modes}</div></div></div></section>`;
}

function mapChips(d) {
  const st = d.stats;
  const lines = st.added || st.removed ? `<span class="chip"><span class="add">+${st.added}</span> <span class="del">−${st.removed}</span> lines</span>` : "";
  const untested = st.untested.length
    ? `<span class="chip warn" title="${esc(st.untested.join("\n"))}">${st.untested.length} edit${st.untested.length > 1 ? "s" : ""} no test imports</span>` : "";
  const deps = depCount(d);
  const radius = deps ? `<span class="chip dep" title="${esc(d.nodes.filter((n) => n.dependent).map((n) => n.id).join("\n"))}"><b>${deps}</b> file${deps > 1 ? "s" : ""} import the edited code</span>` : "";
  const chip = (n, label) => `<span class="chip"><b>${n}</b> ${label}</span>`;
  const opened = st.visited ? chip(st.visited, "visited") + chip(st.read, "read") : "";
  return `<div class="chips">${chip(st.edited, "changed")}${opened}${lines}${radius}${untested}</div>`;
}


function mapSvg(d, s) {
  const S = 300, PAD = 30;
  // Fit the box around all nodes to the panel: a lopsided tree would leave half of it empty.
  const xs = d.nodes.map((n) => n.x), ys = d.nodes.map((n) => n.y);
  const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const scale = (S - 2 * PAD) / Math.max(x1 - x0, y1 - y0, 0.2);
  const at = (n) => [S / 2 + (n.x - (x0 + x1) / 2) * scale, S / 2 + (n.y - (y0 + y1) / 2) * scale];
  const byId = Object.fromEntries(d.nodes.map((n) => [n.id, n]));
  let edges = "", links = "", dots = "";
  const wanted = [];  // [priority, x, y, text, class]; placed later without overlaps
  d.edges.forEach((e) => {
    const [x1, y1] = at(byId[e.from]), [x2, y2] = at(byId[e.to]);
    const hot = byId[e.to].touch || byId[e.to].current;
    edges += `<line class="edge${hot ? " hot" : ""}" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  });
  d.imports.forEach((e) => {
    const [x1, y1] = at(byId[e.from]), [x2, y2] = at(byId[e.to]);
    links += `<line class="link" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"/>`;
  });
  d.nodes.forEach((n) => {
    const [x, y] = at(n);
    const r = n.kind === "root" ? 6 : n.kind === "folder" ? Math.min(7, 2.5 + Math.log2(n.count + 1) * 0.9) : 3;
    const lit = n.touch ? ` lit-${n.touch}` : n.current ? " lit-read" : n.dependent ? " dep" : "";
    const tip = `${n.id || n.name}${n.kind === "folder" ? ` · ${n.count} files` : ""}${n.touch ? ` · ${n.touch === "edit" ? "edited" : "read"} this turn` : ""}${n.dependent ? " · imports an edited file" : ""}`;
    if (n.touch || n.current) dots += `<circle class="glow${lit}" cx="${x}" cy="${y}" r="${r + 7}"/>`;
    dots += `<circle class="node g-${n.kind === "root" ? "root" : groupOf(n.cat)}${lit}" cx="${x}" cy="${y}" r="${r}"><title>${esc(tip)}</title></circle>`;
    if (n.current) return;
    const text = n.kind === "folder" ? `${n.name}/ ${n.count}` : n.name;
    if (n.touch) wanted.push([n.touch === "edit" ? 1 : 2, x, y + r + 9, text, `t-${n.touch}`]);
    else if (n.kind === "root" || (n.kind === "folder" && n.depth === 1)) wanted.push([3, x, y + r + 9, text, ""]);
    else if (n.dependent && depCount(d) <= DEP_LABELS) wanted.push([4, x, y + r + 9, text, "t-dep"]);
  });
  const cur = d.nodes.find((n) => n.current);
  if (cur) {
    const [x, y] = at(cur);
    const verb = VERB[cur.touch] || (s.state === "working" ? "Working on" : "Last on");
    wanted.push([0, x, y - 14, `${s.agent === "codex" ? "Codex" : "Claude"} · ${verb} · ${cur.name}`, "t-current"]);
  }
  return `<svg class="map" viewBox="0 0 ${S} ${S}" role="img" aria-label="Code map of ${esc(d.project)}">
    <defs><filter id="mapglow" x="-1" y="-1" width="3" height="3"><feGaussianBlur stdDeviation="3"/></filter></defs>
    ${edges}${links}${dots}${placeLabels(wanted, S)}</svg>`;
}

// Place labels by priority. A label that would overlap moves up or down a step; a low-priority
// label with no free spot is left out (its name stays in the node's hover title).
function placeLabels(wanted, S) {
  const placed = [], H = 13, out = [];
  const hits = (a) => placed.some((b) => a.x < b.x + b.w + 2 && b.x < a.x + a.w + 2 && a.y < b.y + b.h + 1 && b.y < a.y + a.h + 1);
  wanted.sort((a, b) => a[0] - b[0]).forEach(([priority, x, y, text, cls]) => {
    const t = text.length > 34 ? text.slice(0, 33) + "…" : text;
    const w = t.length * 5.3 + 10;
    for (const dy of [0, 14, -14, 28, -28]) {
      const box = { x: Math.max(2, Math.min(S - w - 2, x - w / 2)), y: Math.max(2, Math.min(S - H - 2, y - H / 2 + dy)), w, h: H };
      if (!hits(box) || priority <= 1 && dy === -28) {  // the current and edited files always show
        placed.push(box);
        out.push(`<g class="lbl ${cls}"><rect x="${box.x}" y="${box.y}" width="${w}" height="${H}" rx="4"/>
          <text x="${box.x + w / 2}" y="${box.y + 9.5}" text-anchor="middle">${esc(t)}</text></g>`);
        return;
      }
    }
  });
  return out.join("");
}

function mapLegend(d) {
  const counts = {};
  d.nodes.filter((n) => n.kind !== "root").forEach((n) => { counts[groupOf(n.cat)] = (counts[groupOf(n.cat)] || 0) + 1; });
  const items = MAP_GROUPS.filter(([g]) => counts[g]).map(([g, label]) => `<span><i class="g-${g}"></i>${label}</span>`).join("");
  return `<div class="map-legend">${items}<span><i class="ring-read"></i>Read</span><span><i class="ring-edit"></i>Edited</span>
    ${d.imports.length ? `<span><i class="dash"></i>Imports it</span>` : ""}</div>`;
}

async function loadMap() {
  const { sid, mode } = ui.map;
  if (!sid) return;
  const data = await api(`/api/map?sid=${encodeURIComponent(sid)}&mode=${mode}`);
  if (ui.map.sid === sid && ui.map.mode === mode) ui.map.data = data;  // ignore an answer for an old pane
}

async function pollMaps() {
  await loadMap().catch(() => {});
}

function setMapMode(mode) {
  ui.map.mode = mode === "uncommitted" ? "uncommitted" : "turn";
  ui.map.data = null;
  render();
  loadMap().then(render).catch(() => {});
}
