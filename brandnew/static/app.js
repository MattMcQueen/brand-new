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
