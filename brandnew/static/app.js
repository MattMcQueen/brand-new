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
