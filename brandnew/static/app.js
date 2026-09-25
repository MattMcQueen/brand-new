// Light/dark toggle. The choice is remembered in this browser only; the page works without it.
(function () {
  var root = document.documentElement;
  var button = document.getElementById("theme-toggle");
  if (!button) return;
  var media = window.matchMedia("(prefers-color-scheme: dark)");

  function isDark() {
    return root.dataset.theme ? root.dataset.theme === "dark" : media.matches;
  }
  function label() {
    var text = isDark() ? "Switch to light mode" : "Switch to dark mode";
    button.setAttribute("aria-label", text);
    button.title = text;
  }
  button.addEventListener("click", function () {
    var next = isDark() ? "light" : "dark";
    root.dataset.theme = next;
    try { localStorage.setItem("theme", next); } catch (e) { /* storage blocked: fine for this visit */ }
    label();
  });
  media.addEventListener("change", label);
  label();
})();

// Ko-fi: the "Support me" button (and the end-of-page link) open Ko-fi's donation form in a
// panel. The form is only created on the first click, so nothing from Ko-fi loads for anyone
// who doesn't ask for it. Without popover support the links simply open Ko-fi in a new tab.
(function () {
  var panel = document.getElementById("kofi-panel");
  if (!panel || typeof panel.showPopover !== "function") return;
  var frameBox = panel.querySelector(".support-frame");

  function load() {
    if (frameBox.firstChild) return;
    var frame = document.createElement("iframe");
    frame.src = panel.dataset.src;
    frame.title = "Support Brand New on Ko-fi";
    frame.loading = "eager";
    frameBox.appendChild(frame);
  }
  document.querySelectorAll("[data-kofi-panel]").forEach(function (link) {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      if (panel.matches(":popover-open")) { panel.hidePopover(); return; }
      load();
      panel.showPopover();
    });
  });
})();

// Keep the "Support me" button from covering other buttons: while a button or small link is
// underneath it, it slides out of the way. Big click targets (like the home page's genre tiles)
// don't count, since covering a corner of one doesn't stop you clicking it.
(function () {
  var btn = document.querySelector(".support-btn");
  if (!btn || typeof document.elementsFromPoint !== "function") return;
  var panel = document.getElementById("kofi-panel");
  var queued = false;

  function coversControl() {
    var r = btn.getBoundingClientRect();
    var limit = r.width * r.height * 4;
    var points = [[r.left + 2, r.top + 2], [r.right - 2, r.top + 2], [r.left + 2, r.bottom - 2],
                  [r.right - 2, r.bottom - 2], [(r.left + r.right) / 2, (r.top + r.bottom) / 2]];
    return points.some(function (p) {
      return document.elementsFromPoint(p[0], p[1]).some(function (el) {
        if (btn.contains(el) || (panel && panel.contains(el))) return false;
        var c = el.closest("a, button, input, select, textarea, summary");
        if (!c) return false;
        var cr = c.getBoundingClientRect();
        return cr.width * cr.height < limit;
      });
    });
  }
  function update() {
    queued = false;
    if (panel && panel.matches(":popover-open")) { btn.classList.remove("is-tucked"); return; }
    btn.classList.remove("is-tucked");  // measure where it would be
    if (coversControl()) btn.classList.add("is-tucked");
  }
  function queue() { if (!queued) { queued = true; requestAnimationFrame(update); } }
  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", queue);
  if (panel) panel.addEventListener("toggle", queue);
  queue();
})();

// "Running late" notice: the pages are rebuilt every morning, so data more than a couple of days
// old means the daily update has been failing. The notice is in every page, hidden; show it then.
(function () {
  var note = document.querySelector(".stale[data-generated]");
  if (!note) return;
  var generated = Date.parse(note.dataset.generated);
  var limit = Number(note.dataset.staleHours) * 3600 * 1000;
  if (!isNaN(generated) && Date.now() - generated > limit) note.hidden = false;
})();

// Genre tiles: a cover that fails to load (the image hosts sometimes have errors) is dropped from
// the fan, rather than leaving a broken-image box. The genre pages have a placeholder instead.
(function () {
  function drop(img) { if (img.closest && img.closest(".tile-fan")) img.remove(); }
  document.addEventListener("error", function (e) { drop(e.target); }, true);
  document.querySelectorAll(".tile-fan img").forEach(function (img) {
    if (img.complete && !img.naturalWidth) drop(img);  // failed before this script ran
  });
})();
