"use strict";
// The activity page: totals, agent time per day (stacked by agent), plan limits, projects.

const TOKEN = new URLSearchParams(location.search).get("t") || "";
const AGENTS = [["claude", "Claude"], ["codex", "Codex"]];  // fixed order: stack order and legend order
const page = document.getElementById("page");
const tip = document.getElementById("tip");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
let days = 7;
let data = null;
// The installed agents only (an older service sends no list: show both).
const shown = () => AGENTS.filter(([a]) => !data.agents?.length || data.agents.includes(a));

async function load() {
  const res = await fetch(`/api/activity?days=${days}`, { headers: { "X-Pitwall-Token": TOKEN } });
  if (!res.ok) throw new Error(`Request failed (${res.status})`);
  data = await res.json();
}

function dayList() {
  const out = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    out.push(d.toLocaleDateString("sv-SE"));  // YYYY-MM-DD in local time
  }
  return out;
}

const sum = (rows, key) => rows.reduce((n, r) => n + r[key], 0);

function tiles(rows) {
  const tile = (label, value, note) => `<div class="tile"><span>${label}</span><b>${value}</b>${note ? `<small>${note}</small>` : ""}</div>`;
  return `<section class="tiles">
    ${tile("Agent time", fmt.duration(sum(rows, "active")), "all agents added up")}
    ${tile("Prompts", fmt.count(sum(rows, "prompts")))}
    ${tile("Files edited", fmt.count(sum(rows, "files")))}
    ${tile("Commands", fmt.count(sum(rows, "commands")))}
    ${tile("Tokens", fmt.tokens(sum(rows, "tokens")), "cache reads included")}</section>`;
}

function chart(rows) {
  const list = dayList();
  const per = list.map((day) => {
    const v = { day };
    AGENTS.forEach(([a]) => { v[a] = sum(rows.filter((r) => r.day === day && r.agent === a), "active") / 3600; });
    v.total = AGENTS.reduce((n, [a]) => n + v[a], 0);
    return v;
  });
  const box = document.querySelector(".chart-box");
  const W = Math.max(300, box ? box.clientWidth - 36 : 600), H = 220, L = 34, B = 26, T = 18;  // 36 = card padding
  const top = Math.max(1, Math.ceil(Math.max(...per.map((p) => p.total)) || 1));
  const step = top > 8 ? Math.ceil(top / 4) : top > 4 ? 2 : 1;
  const y = (h) => T + (H - T - B) * (1 - h / top);
  const band = (W - L) / per.length, bw = Math.min(42, band * 0.62);
  let svg = "";
  for (let h = 0; h <= top; h += step) {
    svg += `<line class="grid" x1="${L}" x2="${W}" y1="${y(h)}" y2="${y(h)}"/><text class="axis" x="${L - 6}" y="${y(h) + 3.5}" text-anchor="end">${h}h</text>`;
  }
  per.forEach((p, i) => {
    const x = L + band * i + (band - bw) / 2;
    let base = 0;
    const parts = AGENTS.filter(([a]) => p[a] > 0);
    parts.forEach(([a], k) => {
      const y0 = y(base), y1 = y(base + p[a]);
      const gap = k > 0 ? 2 : 0;  // 2px surface gap between stacked segments
      const h = Math.max(1, y0 - y1 - gap), isTop = k === parts.length - 1, r = Math.min(4, h / 2);
      svg += isTop
        ? `<path class="s-${a}" d="M${x},${y1 + h} V${y1 + r} Q${x},${y1} ${x + r},${y1} H${x + bw - r} Q${x + bw},${y1} ${x + bw},${y1 + r} V${y1 + h} Z"/>`
        : `<rect class="s-${a}" x="${x}" y="${y1}" width="${bw}" height="${h}"/>`;
      base += p[a];
    });
    if (days <= 14 && p.total > 0) svg += `<text class="val" x="${x + bw / 2}" y="${y(p.total) - 6}" text-anchor="middle">${fmt.duration(p.total * 3600)}</text>`;
    const label = new Date(p.day + "T12:00").toLocaleDateString("en-GB", days <= 7 ? { weekday: "short", day: "numeric" } : { day: "numeric" });
    svg += `<text class="axis" x="${x + bw / 2}" y="${H - 8}" text-anchor="middle">${label}</text>`;
    svg += `<rect class="hit" data-i="${i}" x="${L + band * i}" y="${T}" width="${band}" height="${H - T - B}"/>`;
  });
  const legend = shown().map(([a, n]) => `<span><i class="s-${a}"></i>${n}</span>`).join("");
  chart.per = per;
  return `<div class="card-head"><h2>Agent time per day</h2><div class="legend">${legend}</div></div>
    <svg class="chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Agent time per day, stacked by agent">${svg}</svg>`;
}

function limitsCard() {
  const l = data.limits;
  return `<section class="panel-card"><div class="card-head"><h2>Plan limits</h2></div>
    <div class="usage-card wide">${shown().map(([a]) => limitsBlock(a, l[a])).join("")}</div></section>`;
}

function projects(rows) {
  const by = {};
  rows.forEach((r) => {
    const p = by[r.project] ||= { project: r.project, active: 0, claude: 0, codex: 0, prompts: 0, files: 0, commands: 0, tokens: 0 };
    ["active", "prompts", "files", "commands", "tokens"].forEach((k) => { p[k] += r[k]; });
    p[r.agent] += r.active;
  });
  const list = Object.values(by).sort((a, b) => b.active - a.active);
  const body = list.map((p) => `<tr><th scope="row">${esc(p.project)}</th><td>${fmt.duration(p.active)}</td>
    ${shown().map(([a]) => `<td>${p[a] ? fmt.duration(p[a]) : "–"}</td>`).join("")}
    <td>${fmt.count(p.prompts)}</td><td>${fmt.count(p.files)}</td><td>${fmt.count(p.commands)}</td><td>${fmt.tokens(p.tokens)}</td></tr>`).join("");
  return `<section class="panel-card"><div class="card-head"><h2>Projects</h2></div><div class="table-wrap"><table>
    <thead><tr><th scope="col">Project</th><th scope="col">Agent time</th>${shown().map(([, n]) => `<th scope="col">${n}</th>`).join("")}
    <th scope="col">Prompts</th><th scope="col">Files</th><th scope="col">Commands</th><th scope="col">Tokens</th></tr></thead>
    <tbody>${body}</tbody></table></div></section>`;
}

function render() {
  const rows = data.rows;
  page.innerHTML = rows.length
    ? tiles(rows) + `<div class="two"><section class="panel-card chart-box"></section>${limitsCard()}</div>` + projects(rows)
    : `<div class="empty-state"><strong>No agent activity</strong>Nothing in the last ${days} days.</div>` + limitsCard();
  const box = document.querySelector(".chart-box");
  if (box) box.innerHTML = chart(rows);  // drawn after layout, at the card's real width
}

page.addEventListener("mousemove", (e) => {
  const hit = e.target.closest(".hit");
  if (!hit) { tip.classList.remove("show"); return; }
  const p = chart.per[Number(hit.dataset.i)];
  const date = new Date(p.day + "T12:00").toLocaleDateString("en-GB", { weekday: "long", day: "numeric", month: "short" });
  tip.innerHTML = `<b>${date}</b>${shown().map(([a, n]) => `<span><i class="s-${a}"></i>${n}<em>${fmt.duration(p[a] * 3600)}</em></span>`).join("")}
    <span class="sum">Total<em>${fmt.duration(p.total * 3600)}</em></span>`;
  tip.style.left = `${Math.min(e.clientX + 14, innerWidth - 190)}px`;
  tip.style.top = `${e.clientY + 14}px`;
  tip.classList.add("show");
});
page.addEventListener("mouseleave", () => tip.classList.remove("show"));

document.querySelector(".range").addEventListener("click", async (e) => {
  const b = e.target.closest("[data-days]");
  if (!b) return;
  days = Number(b.dataset.days);
  document.querySelectorAll(".range button").forEach((x) => x.classList.toggle("on", x === b));
  await refresh();
});

async function refresh() {
  try { await load(); render(); } catch (e) { page.innerHTML = `<div class="empty-state"><strong>Pitwall is not running</strong>${esc(e.message)}</div>`; }
}
addEventListener("resize", () => data && render());
refresh();
setInterval(() => { if (!document.hidden) refresh(); }, 60000);
