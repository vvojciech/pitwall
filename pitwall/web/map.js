"use strict";
// The code map panel on a card: folders as a radial star map, touched files lit, blast radius dashed.

// Four hues that pass the all-pairs colour check on the map's dark surface; the rest is "Other".
const MAP_GROUPS = [["frontend", "Frontend", ["frontend", "assets"]], ["backend", "Backend & data", ["backend", "database"]],
  ["tests", "Tests", ["tests"]], ["config", "Config", ["config"]], ["other", "Other", ["code", "docs"]]];
const groupOf = (cat) => (MAP_GROUPS.find(([, , cats]) => cats.includes(cat)) || ["other"])[0];
const VERB = { edit: "Editing", read: "Reading" };
const DEP_LABELS = 4;  // above this many dependents, a chip counts them and their labels stay off
const depCount = (d) => d.nodes.filter((n) => n.dependent).length;

function mapPanel(s) {
  const m = ui.map[s.sid];
  if (!m) return "";
  const modes = [["overview", "Overview"], ["files", "Files"]].map(([v, l]) =>
    `<button class="${m.mode === v ? "on" : ""}" data-act="map-mode" data-value="${v}">${l}</button>`).join("");
  let body;
  if (!m.data) body = `<p class="map-note">Reading the project…</p>`;
  else if (m.data.error) body = `<p class="map-note">${esc(m.data.error)}</p>`;
  else body = mapChips(m.data) + mapSvg(m.data, s) + mapLegend(m.data);
  return `<div class="map-panel" data-stop>${body}<div class="map-foot"><div class="seg">${modes}</div></div></div>`;
}

function mapChips(d) {
  const st = d.stats;
  const turn = st.added || st.removed ? `<span class="chip"><span class="add">+${st.added}</span> <span class="del">−${st.removed}</span> this turn</span>` : "";
  const untested = st.untested.length
    ? `<span class="chip warn" title="${esc(st.untested.join("\n"))}">${st.untested.length} edit${st.untested.length > 1 ? "s" : ""} no test imports</span>` : "";
  const deps = depCount(d);
  const radius = deps ? `<span class="chip dep" title="${esc(d.nodes.filter((n) => n.dependent).map((n) => n.id).join("\n"))}"><b>${deps}</b> file${deps > 1 ? "s" : ""} import the edited code</span>` : "";
  return `<div class="chips"><span class="chip"><b>${fmtCount(st.files)}</b> files</span><span class="chip"><b>${st.visited}</b> visited</span>
    <span class="chip"><b>${st.edited}</b> edited</span>${turn}${radius}${untested}</div>`;
}

const fmtCount = (n) => n.toLocaleString("en-US");

function mapSvg(d, s) {
  const S = 300, C = S / 2, R = C - 34;  // viewBox size, centre, usable radius
  const at = (n) => [C + n.x * R, C + n.y * R];
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

async function loadMap(sid) {
  const m = ui.map[sid];
  if (!m) return;
  const data = await api(`/api/map?sid=${encodeURIComponent(sid)}&mode=${m.mode}`);
  if (ui.map[sid] === m) m.data = data;
}

async function pollMaps() {
  await Promise.all(Object.keys(ui.map).map((sid) => loadMap(sid).catch(() => {})));
}
