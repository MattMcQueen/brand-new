// Runs in <head>, before the page is drawn (kept out of the HTML so the Content Security Policy
// can forbid inline scripts).
// 1. Apply a saved light/dark choice straight away, so the page doesn't flash the other theme.
try {
  var t = localStorage.getItem("theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch (e) { /* storage blocked: follow the system setting */ }
// 2. A cover that fails to load (the image hosts sometimes have errors) is removed, rather than
//    leaving a broken-image box: in a genre tile's fan a hidden spare moves up in its place
//    (style.css shows the first three). A card has no spare, so it tries twice more first: the
//    Cover Art Archive sends each request to one of several copies, and some can be broken while
//    others work. The card shows its made-up cover (books) or the record (albums) meanwhile,
//    and keeps it if every try fails.
//    Runs here, not in app.js, so it's listening before any cover starts loading.
document.addEventListener("error", function (e) {
  var img = e.target, tries;
  if (!img || img.tagName !== "IMG" || !img.closest || !img.closest(".tile-fan, .cover")) return;
  tries = Number(img.dataset.tries || 0);
  if (!img.closest(".cover") || tries >= 2) { img.remove(); return; }
  img.dataset.tries = tries + 1;
  img.classList.add("is-retrying");
  var src = (img.currentSrc || img.src).replace(/[?&]retry=\d+$/, "");
  img.removeAttribute("srcset");  // retry the size the browser chose, and only that
  img.src = src + (src.indexOf("?") < 0 ? "?" : "&") + "retry=" + (tries + 1);  // not a cached failure
}, true);
// 3. A card's cover fills its box, trimming the edges. A cover that's a very different shape (a
//    landscape picture book, a square box set) would lose too much, so it's shown whole instead.
document.addEventListener("load", function (e) {
  var img = e.target, box;
  if (!img.classList) return;
  img.classList.remove("is-retrying");
  box = img.closest && img.closest(".cover");
  if (box && img.naturalWidth && box.clientWidth &&
      Math.abs((img.naturalHeight / img.naturalWidth) / (box.clientHeight / box.clientWidth) - 1) > 0.15) {
    img.classList.add("is-odd-shape");
  }
}, true);
