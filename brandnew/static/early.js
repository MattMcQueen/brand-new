// Runs in <head>, before the page is drawn (kept out of the HTML so the Content Security Policy
// can forbid inline scripts).
// 1. Apply a saved light/dark choice straight away, so the page doesn't flash the other theme.
try {
  var t = localStorage.getItem("theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) { /* storage blocked: follow the system setting */ }
// 2. A cover that fails to load is removed, leaving the card's book or record icon behind it.
document.addEventListener("error", function (e) {
  var img = e.target;
  if (img && img.tagName === "IMG" && img.parentNode && img.parentNode.classList.contains("cover")) img.remove();
}, true);
