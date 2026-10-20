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
    if (d.toDateString() === new Date().toDateString()) return time;
    // Past six days a weekday alone is ambiguous, so add the date.
    const far = epoch - Date.now() / 1000 > 6 * 86400;
    return `${d.toLocaleDateString("en-GB", far ? { weekday: "short", day: "numeric", month: "short" } : { weekday: "short" })} ${time}`;
  },
};

// How much of the limit's window has passed, in percent; null without a reset time.
function passed(w) {
  if (!w.resets_at || !w.window) return null;
  const left = w.resets_at - Date.now() / 1000;
  return Math.max(0, Math.min(100, Math.round(100 * (1 - left / w.window))));
}

// Two layers in one track: the time passed in the window (faint, a tick at its end), then the share used.
// A used fill past the tick means the limit goes faster than the window.
function bars(used, time, level) {
  const tick = time == null ? "" : `<span class="time" style="width:${time}%"></span>`;
  return `${tick}<span class="used ${level}" style="width:${Math.max(used, 1)}%"></span>${time == null ? "" : `<i class="tick" style="left:${time}%"></i>`}`;
}

function paceText(used, time) {
  if (time == null) return "";
  return `, ${time}% of the window passed${used > time + 5 ? " (ahead of the clock)" : ""}`;
}

function meter(label, w) {
  if (!w || w.used == null) return "";
  const used = Math.max(0, Math.min(100, Math.round(w.used)));
  const level = used >= 90 ? "crit" : used >= 75 ? "warn" : "ok";
  const time = passed(w);
  return `<div class="meter-row" title="${used}% used${paceText(used, time)}"><span class="mlabel">${label}</span>
    <div class="meter" role="meter" aria-label="${label}: ${used}% used${paceText(used, time)}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${used}">
      ${bars(used, time, level)}</div>
    <span class="mval ${level}">${used}%</span><span class="mreset">${w.resets_at ? `resets ${fmt.reset(w.resets_at)}` : ""}</span></div>`;
}

// Codex credits, shown only when there are some.
function creditsText(l) {
  const c = l && l.credits;
  if (!c || !(c.has_credits || c.unlimited)) return "";
  return c.unlimited ? "Unlimited credits" : `${c.balance} credits`;
}

function windowsText(l) {
  return l && l.windows_left && l.week ? `${l.windows_left} five-hour windows until the weekly reset` : "";
}

function limitsBlock(agent, l) {
  const name = agent === "claude" ? "Claude" : "Codex";
  const notes = [creditsText(l), windowsText(l)].filter(Boolean);
  const body = l ? meter("5 hours", l.five_hour) + meter("Week", l.week) + notes.map((n) => `<p class="mnote">${n}</p>`).join("")
    : `<p class="mnone">${agent === "claude" ? "Shows after Claude Code's next reply." : "Shows after Codex's next reply."}</p>`;
  return `<div class="limits"><span class="agent ${agent}">${name}</span>${body}</div>`;
}

// The compact strip pinned to the bottom of the panel: one row per agent, then today's totals.
function miniMeter(label, w) {
  if (!w || w.used == null) return `<span class="mm none"><em>${label}</em><b>–</b></span>`;
  const used = Math.max(0, Math.min(100, Math.round(w.used)));
  const level = used >= 90 ? "crit" : used >= 75 ? "warn" : "ok";
  const reset = w.resets_at ? `, resets ${fmt.reset(w.resets_at)}` : "";
  const time = passed(w);
  return `<span class="mm" title="${label === "5h" ? "5-hour window" : "Week"}: ${used}% used${paceText(used, time)}${reset}"><em>${label}</em>
    <span class="meter">${bars(used, time, level)}</span><b class="${level}">${used}%</b></span>`;
}

function usageBar() {
  const u = ui.usage;
  if (!u) return "";
  const row = (agent, name) => {
    const l = u.limits[agent];
    const extra = creditsText(l);
    return `<div class="urow"><span class="agent ${agent}">${name}</span>${miniMeter("5h", l && l.five_hour)}${miniMeter("wk", l && l.week)}</div>${
      extra ? `<div class="urow unote" title="${windowsText(l)}"><span></span><span class="tval">${extra}</span></div>` : ""}`;
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
