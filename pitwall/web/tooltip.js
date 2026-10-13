"use strict";
// Instant tooltips. The browser waits about a second before it shows a title, so this moves each
// title to data-tip on hover and shows it at once. Render code can set title again; the next hover moves it.
(() => {
  const tip = document.createElement("div");
  tip.className = "hover-tip";
  tip.setAttribute("role", "tooltip");
  document.body.append(tip);
  let target = null;

  function hide() {
    target = null;
    tip.classList.remove("show");
  }

  function show(el) {
    if (el.hasAttribute("title")) {
      el.dataset.tip = el.title;
      if (!el.hasAttribute("aria-label")) el.setAttribute("aria-description", el.title);
      el.removeAttribute("title");
    }
    if (!el.dataset.tip) return hide();
    target = el;
    tip.textContent = el.dataset.tip;
    tip.classList.add("show");
    const r = el.getBoundingClientRect(), t = tip.getBoundingClientRect();
    const left = Math.min(Math.max(4, r.left + r.width / 2 - t.width / 2), innerWidth - t.width - 4);
    const below = r.bottom + 6 + t.height < innerHeight;
    tip.style.left = `${left}px`;
    tip.style.top = `${below ? r.bottom + 6 : r.top - t.height - 6}px`;
  }

  document.addEventListener("mouseover", (e) => {
    const el = e.target.closest?.("[title], [data-tip]");
    if (el !== target) el ? show(el) : hide();
  });
  document.addEventListener("focusin", (e) => { if (e.target.matches?.("[title], [data-tip]")) show(e.target); });
  document.addEventListener("focusout", hide);
  document.addEventListener("scroll", hide, true);
  // A re-render can remove the hovered element; drop the tip with it.
  new MutationObserver(() => { if (target && !target.isConnected) hide(); }).observe(document.body, { childList: true, subtree: true });
})();
