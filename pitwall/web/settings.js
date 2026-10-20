"use strict";
// Settings: switch optional features off. The service keeps them in ~/.pitwall/settings.json. Uses app.js globals.

function settingsForm() {
  const f = ui.settingsForm;
  if (!f) return "";
  if (!f.features) return `<section class="settings-form panel"><p>Reading the settings…</p></section>`;
  const groups = [...new Set(f.features.map((x) => x.group))].map((group) => {
    const rows = f.features.filter((x) => x.group === group).map((x) => `<label class="check"${x.hint ? ` title="${esc(x.hint)}"` : ""}>
        <input type="checkbox" data-setting="${esc(x.key)}" ${featureOn(x.key) && !x.locked ? "checked" : ""}${x.locked ? " disabled" : ""}>
        <span>${esc(x.label)}${x.locked ? ` <em>off by ${esc(x.locked)}</em>` : ""}</span></label>`).join("");
    return `<h3>${esc(group)}</h3>${rows}`;
  }).join("");
  return `<section class="settings-form panel">${groups}
    <div class="row"><button class="btn" data-setting-close>Close</button></div></section>`;
}

async function toggleSettings() {
  if (ui.settingsForm) { ui.settingsForm = null; return render(); }
  ui.settingsForm = {};
  render();
  try { ui.settingsForm.features = (await api("/api/settings")).features; } catch (e) { ui.settingsForm = null; toast(e.message); }
  render();
}

async function saveSetting(input) {
  input.blur();  // a focused input holds back the next render
  input.disabled = true;
  try {
    const res = await api("/api/settings", { [input.dataset.setting]: input.checked });
    if (ui.settingsForm) ui.settingsForm.features = res.features;
  } catch (e) { toast(e.message); }
  await poll();  // the new settings arrive with the state; a failed save snaps the box back
  if (featureOn("ports")) await pollPorts();
  if (featureOn("plan_limits")) await pollUsage();
  render();
}

// Loads before app.js, so render() always finds settingsForm.
document.getElementById("settings").addEventListener("click", toggleSettings);
document.getElementById("cards").addEventListener("change", (e) => { if ("setting" in e.target.dataset) saveSetting(e.target); });
document.getElementById("cards").addEventListener("click", (e) => { if (e.target.closest("[data-setting-close]")) toggleSettings(); });
