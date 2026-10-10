"use strict";
// Plan limit meters and number formats, shared by the sidebar and the activity page.

const fmt = {
  duration(sec) {
    const m = Math.round(sec / 60);
    if (m < 60) return `${m}m`;
    return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
  },
  count: (n) => n.toLocaleString("en-US"),
  tokens(n) {
    if (n >= 1e9) return `${(n / 1e9).toFixed(1)}B`;
    if (n >= 1e6) return `${(n / 1e6).toFixed(n >= 1e8 ? 0 : 1)}M`;
    if (n >= 1e3) return `${(n / 1e3).toFixed(n >= 1e5 ? 0 : 1)}k`;
    return String(n);
  },
  reset(epoch) {
    if (!epoch) return "";
    const d = new Date(epoch * 1000);
    const time = d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
    return d.toDateString() === new Date().toDateString() ? time : `${d.toLocaleDateString("en-GB", { weekday: "short" })} ${time}`;
  },
};

function meter(label, w) {
  if (!w || w.used == null) return "";
  const used = Math.max(0, Math.min(100, Math.round(w.used)));
  const level = used >= 90 ? "crit" : used >= 75 ? "warn" : "ok";
  return `<div class="meter-row"><span class="mlabel">${label}</span>
    <div class="meter" role="meter" aria-label="${label}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${used}">
      <span class="${level}" style="width:${Math.max(used, 1)}%"></span></div>
    <span class="mval ${level}">${used}%</span><span class="mreset">${w.resets_at ? `resets ${fmt.reset(w.resets_at)}` : ""}</span></div>`;
}

function limitsBlock(agent, l) {
  const name = agent === "claude" ? "Claude" : "Codex";
  const body = l ? meter("5 hours", l.five_hour) + meter("Week", l.week)
    : `<p class="mnone">${agent === "claude" ? "Shows after Claude Code's next reply." : "Shows after Codex's next reply."}</p>`;
  return `<div class="limits"><span class="agent ${agent}">${name}</span>${body}</div>`;
}

// The compact strip pinned to the bottom of the panel: one row per agent, then today's totals.
function miniMeter(label, w) {
  if (!w || w.used == null) return `<span class="mm none"><em>${label}</em><b>–</b></span>`;
  const used = Math.max(0, Math.min(100, Math.round(w.used)));
  const level = used >= 90 ? "crit" : used >= 75 ? "warn" : "ok";
  const reset = w.resets_at ? `, resets ${fmt.reset(w.resets_at)}` : "";
  return `<span class="mm" title="${label === "5h" ? "5-hour window" : "Week"}: ${used}% used${reset}"><em>${label}</em>
    <span class="meter"><span class="${level}" style="width:${Math.max(used, 2)}%"></span></span><b class="${level}">${used}%</b></span>`;
}

function usageBar() {
  const u = ui.usage;
  if (!u) return "";
  const row = (agent, name) => {
    const l = u.limits[agent];
    return `<div class="urow"><span class="agent ${agent}">${name}</span>${miniMeter("5h", l && l.five_hour)}${miniMeter("wk", l && l.week)}</div>`;
  };
  const t = u.today;
  const today = t.active || t.prompts ? `${fmt.duration(t.active)} · ${fmt.count(t.prompts)} prompts` : "No activity yet";
  const detail = `Today: ${fmt.duration(t.active)} agent time, ${fmt.count(t.prompts)} prompts, ${fmt.tokens(t.tokens)} tokens, ${fmt.count(t.commands)} commands`;
  const rows = [["claude", "Claude"], ["codex", "Codex"]].filter(([a]) => (u.agents || [a]).includes(a));
  return `${rows.map(([a, n]) => row(a, n)).join("")}
    <div class="urow today-row" title="${detail}"><span>Today</span><span class="tval">${today}</span><button class="link" data-usage="open">Activity ›</button></div>`;
}

async function pollUsage() {
  try { ui.usage = await api("/api/activity?days=1"); } catch { ui.usage = null; }
}
