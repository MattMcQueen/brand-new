"""Forthcoming science fiction, fantasy and horror from the ISFDB (isfdb.org, CC BY 4.0).

Google Books lists little new science fiction, so this adds the ISFDB's Monthly Bibliography:
books by exact release date, with ISBNs. Most aren't genre-tagged before publication, so each
new ISBN is looked up once on Google Books, whose full record has detailed subjects ("Fiction /
Science Fiction / Space Opera"), and filed under whichever of our genres those match.

The ISFDB asks crawlers to leave 1000 seconds between requests, so each run fetches just one
month page, the one fetched longest ago; the others come from the cache. Month pages and
lookups are kept in one cache file between runs.
"""
import html
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlencode

from .. import amazon, config, net
from ..models import Release
from ..ukdates import fetch_window, in_fetch_window
from . import google_books as gb

MONTH_URL = "https://www.isfdb.org/cgi-bin/fc.cgi?date+{month}+{year}"
TYPES = {"Novel", "Collection", "Anthology"}  # not chapbooks, omnibuses, magazines or nonfiction
ENGLISH_ISBN = ("9780", "9781", "9798")      # English-language ISBN ranges (979-8 is the US)
MAX_LOOKUPS = 75       # new books looked up per run, 2 Google Books calls each (plus 450 for the main fetch)
RECHECK_DAYS = 7       # a book Google didn't know (or couldn't file) is looked up again after this

# When Google has no subjects for a book, the ISFDB's own tags (adult sections only)
TAG_GENRES = {
    "science-fiction": re.compile(r"\b(science fiction|hard sf|military sf|space opera|cyberpunk|time travel)\b", re.I),
    "fantasy": re.compile(r"(?<!juvenile )(?<!young-adult )\b(fantasy|romantasy)\b", re.I),
    "horror": re.compile(r"(?<!juvenile )(?<!young-adult )\bhorror\b", re.I),
}

_ROW = re.compile(r'<tr align=left class="table[12]">(.*?)</tr>', re.S)
_CELL = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_SECTION = re.compile(r'<h2 id = "(\w+)"')


def _text(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def isbn13(s: str) -> str | None:
    """"978-1-250-37527-8" or an ISBN-10 -> 13 digits; None for catalogue numbers."""
    d = re.sub(r"[^0-9Xx]", "", s)
    if len(d) == 13 and d.isdigit():
        return d
    if len(d) == 10 and d[:9].isdigit():
        core = "978" + d[:9]
        check = (10 - sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core)) % 10) % 10
        return core + str(check)
    return None


def parse_month(page: str) -> list[dict]:
    """The rows of a Monthly Bibliography page, with the section each is in (adult, ya, romance)."""
    sections = [(m.start(), m.group(1)) for m in _SECTION.finditer(page)]
    rows = []
    for m in _ROW.finditer(page):
        cells = _CELL.findall(m.group(1))
        if len(cells) < 8:
            continue
        pub = re.search(r'href="(https://www\.isfdb\.org/cgi-bin/pl\.cgi\?\d+)"[^>]*>(.*?)</a>', cells[2], re.S)
        if not pub:
            continue
        rows.append({
            "date": _text(cells[0]),
            "authors": [_text(a) for a in re.findall(r'ea\.cgi\?\d+"[^>]*>(.*?)</a>', cells[1], re.S)],
            "title": _text(pub.group(2)),
            "url": pub.group(1),
            "reprint": bool(_text(cells[3])),
            "tags": [t.strip() for t in _text(cells[4]).split(",") if t.strip()],
            "type": _text(cells[5]),
            "publisher": _text(cells[6]),
            "isbn": isbn13(_text(cells[7])),
            "format": _text(cells[10]).split(" ")[0] if len(cells) > 10 else "",  # hc, tp, pb, ebook...
            "section": next((name for pos, name in reversed(sections) if pos < m.start()), "adult"),
        })
    return rows


def months_in_window(today: date) -> list[str]:
    """"YYYY-MM" for every month the fetch window touches, this month first."""
    start, end = fetch_window(today)
    months, d = [], start.replace(day=1)
    while d <= end:
        months.append(f"{d:%Y-%m}")
        d = (d + timedelta(days=32)).replace(day=1)
    return sorted(months, key=lambda m: (m != f"{today:%Y-%m}", m))


def genres_for(categories: list[str], tags: list[str], section: str) -> list[str]:
    """Our book genres for a book: from Google's subjects if it has any, else the ISFDB's tags."""
    if categories:
        cats = [c.lower() for c in categories]
        return [g.slug for g in config.BOOK_GENRES if any(c.startswith(t) for c in cats for t in g.terms)]
    if section not in ("adult", "romance"):
        return []
    text = ", ".join(tags)
    return [slug for slug, pattern in TAG_GENRES.items() if pattern.search(text)]


def lookup(isbn: str, key: str, get_json) -> dict:
    """Google Books' subjects, language and cover for an ISBN (2 calls: search, then the full record,
    since search results only say "Fiction")."""
    found = (get_json(gb.API + "?" + urlencode({"q": f"isbn:{isbn}", "country": "GB", "key": key})) or {}).get("items")
    if not found:
        return {"categories": [], "language": None, "cover": None}
    v = (get_json(f"{gb.API}/{found[0]['id']}?" + urlencode({"country": "GB", "key": key})) or {}).get("volumeInfo", {})
    img = (v.get("imageLinks") or {}).get("thumbnail")
    return {"categories": v.get("categories") or [], "language": v.get("language"),
            "cover": img.replace("http://", "https://").replace("&edge=curl", "") if img else None}


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fetch(today: date, cache_path: Path, get_json=None, get_text=None) -> list[Release]:
    get_json = get_json or net.get_json
    get_text = get_text or net.get_text
    cache = _load(cache_path)
    months = {m: v for m, v in cache.get("months", {}).items() if m in months_in_window(today)}
    books = cache.get("books", {})

    # One month page per run: the one fetched longest ago (never fetched counts as oldest)
    due = min(months_in_window(today), key=lambda m: months.get(m, {}).get("fetched", ""))
    year, month = due.split("-")
    try:
        rows = parse_month(get_text(MONTH_URL.format(month=int(month), year=year)))
        months[due] = {"fetched": today.isoformat(), "rows": rows}
        print(f"  ISFDB: {len(rows)} entries for {due}", file=sys.stderr)
    except RuntimeError as e:
        print(f"! ISFDB {due}: {e}; using the cached months", file=sys.stderr)

    rows = [r for m in months.values() for r in m["rows"]
            if r["type"] in TYPES and not r["reprint"] and r["isbn"] and r["isbn"].startswith(ENGLISH_ISBN)
            and (d := gb.exact_date(r["date"])) and in_fetch_window(d, today)]
    # One row per book: editions (hardback, ebook, large print) are listed separately. Print first.
    best: dict[tuple, dict] = {}
    for r in sorted(rows, key=lambda r: (r["format"] == "ebook", r["date"])):
        best.setdefault((r["title"].lower(), r["authors"][0].lower() if r["authors"] else ""), r)
    rows = list(best.values())

    # Look up new ISBNs (soonest first), and ones Google didn't know last time
    stale = (today - timedelta(days=RECHECK_DAYS)).isoformat()
    todo = sorted((r for r in rows if r["isbn"] not in books or
                   (not books[r["isbn"]]["categories"] and books[r["isbn"]]["checked"] < stale)),
                  key=lambda r: r["date"])
    looked = 0
    if todo:
        key = gb.api_key()
        for r in todo[:MAX_LOOKUPS]:
            try:
                books[r["isbn"]] = lookup(r["isbn"], key, get_json) | {"checked": today.isoformat()}
                looked += 1
            except net.QuotaExhausted as e:
                print(f"! ISFDB lookups: {e}; stopping", file=sys.stderr)
                break
            except RuntimeError as e:
                print(f"! ISFDB lookup {r['isbn']}: {e}", file=sys.stderr)

    out = []
    for r in rows:
        info = books.get(r["isbn"])
        if not info or info["language"] not in ("en", None):
            continue
        genres = genres_for(info["categories"], r["tags"], r["section"])
        if not genres or not r["authors"]:
            continue
        by = ", ".join(r["authors"][:2])
        out.append(Release(kind="books", id=r["isbn"], title=r["title"], by=by, date=gb.exact_date(r["date"]),
                           source="isfdb", amazon_url=amazon.book_url(r["title"], by), genres=genres,
                           cover=info["cover"], publisher=r["publisher"], info_url=r["url"]))

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"months": months, "books": books}), encoding="utf-8")
    print(f"  ISFDB: {len(out)} books in our genres, {looked} new lookups", file=sys.stderr)
    return out
