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

// Genre chips: on phones they're one row that scrolls sideways, so start with the current genre in view.
(function () {
  var row = document.querySelector(".chips"), current = row && row.querySelector("[aria-current]");
  if (row && current && row.scrollWidth > row.clientWidth)
    row.scrollLeft = current.getBoundingClientRect().left - row.getBoundingClientRect().left - 16;
})();

// "Surprise me": picks a random release from the last week (with a cover) and shows it, after a
// quick shuffle through other covers. On a genre page (data-genre) it picks from that page's own
// cards instead, just out and coming soon. The data file is only fetched on the first click.
(function () {
  var buttons = document.querySelectorAll("[data-surprise]");
  var box = document.getElementById("surprise");
  if (!buttons.length || !box || typeof box.showPopover !== "function" || !window.fetch) return;
  var img = box.querySelector(".surprise-cover img");
  var go = box.querySelector(".surprise-go");
  var data = null, kind = "", genre = "", timer = null, runs = 0;

  function load() {
    if (data) return Promise.resolve(data);
    return fetch("/data/releases.json").then(function (r) { return r.json(); }).then(function (d) { data = d; return d; });
  }
  // The same "last week" as the pages: the seven days up to the day the data was built.
  function choices() {
    if (genre) {
      var onPage = {};
      document.querySelectorAll(".card[data-id]").forEach(function (c) { onPage[c.dataset.id] = true; });
      return data.releases.filter(function (r) {
        return r.cover && r.kind === kind && onPage[r.id] && r.genres.indexOf(genre) >= 0;
      });
    }
    var end = data.generated.slice(0, 10);
    var start = new Date(end + "T00:00:00Z");
    start.setUTCDate(start.getUTCDate() - 7);
    start = start.toISOString().slice(0, 10);
    return data.releases.filter(function (r) {
      return r.cover && r.genres.length && r.date >= start && r.date <= end && (!kind || r.kind === kind);
    });
  }
  function any(list) { return list[Math.floor(Math.random() * list.length)]; }
  function reveal(r) {
    box.querySelector(".surprise-title").textContent = r.title;
    box.querySelector(".surprise-by").textContent = r.by;
    box.querySelector(".surprise-date").textContent = (r.date > data.generated.slice(0, 10) ? "Due " : "Out ") +
      new Date(r.date + "T00:00:00Z").toLocaleDateString("en-GB", { day: "numeric", month: "long", timeZone: "UTC" });
    go.href = "/" + r.kind + "/" + (genre || r.genres[0]) + "/#pick-" + encodeURIComponent(r.id);
    go.setAttribute("aria-label", "See " + r.title + " by " + r.by);
    box.classList.remove("is-shuffling");
  }
  // Shuffles covers until at least ten have flicked past AND the chosen cover has loaded, so the
  // cover shown always belongs to the title. A cover that fails to load means choosing again.
  function surprise() {
    load().then(function () {
      var list = choices();
      if (!list.length) return;
      var run = ++runs, flips = 0, landed = null;
      if (!box.matches(":popover-open")) box.showPopover();
      box.classList.add("is-shuffling");
      clearInterval(timer);
      timer = setInterval(function () {
        if (run !== runs) return;
        if (++flips >= 10 && landed) {
          clearInterval(timer);
          img.src = landed.cover;
          reveal(landed);
        } else {
          img.src = any(list).cover;
        }
      }, 90);
      (function choose() {
        if (!list.length) { clearInterval(timer); box.hidePopover(); return; }  // no cover would load
        var pick = any(list), probe = new Image();
        probe.referrerPolicy = "no-referrer";
        probe.onload = function () { if (run === runs) landed = pick; };
        probe.onerror = function () { list = list.filter(function (r) { return r !== pick; }); choose(); };
        probe.src = pick.cover;
      })();
    }).catch(function () { /* no data: the button just does nothing */ });
  }
  buttons.forEach(function (b) {
    if (b.dataset.genre && !document.querySelector(".card .cover img")) return;  // nothing with a cover to pick
    b.hidden = false;
    b.addEventListener("click", function () { kind = b.dataset.surprise; genre = b.dataset.genre || ""; surprise(); });
  });
  box.querySelector(".surprise-again").addEventListener("click", surprise);
})();

// Arriving from "Surprise me" (#pick-<id>): scroll to that release's card and make it wiggle.
// On a genre page the pick is on the same page, so this runs again when the address changes.
(function () {
  if (!window.CSS || !CSS.escape) return;
  function show() {
    if (location.hash.indexOf("#pick-") !== 0) return;
    var id = decodeURIComponent(location.hash.slice(6));
    var card = document.querySelector('.card[data-id="' + CSS.escape(id) + '"]');
    if (!card) return;
    var box = document.getElementById("surprise");
    if (box && box.matches && box.matches(":popover-open")) box.hidePopover();
    document.querySelectorAll(".card.is-picked").forEach(function (c) { c.classList.remove("is-picked"); });
    void card.offsetWidth;  // restart the wiggle if it's the same card again
    card.scrollIntoView({ block: "center" });
    card.classList.add("is-picked");
  }
  show();
  window.addEventListener("hashchange", show);
})();
