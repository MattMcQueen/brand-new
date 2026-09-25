"""New and upcoming books from the Google Books API.

Only queries with a year in them respect orderBy=newest, and each query stops at roughly 150
results, so every genre runs several variations of subject:"fiction / <genre>" <year> and keeps
books with an exact publication date inside the window.
"""
import os
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

from .. import amazon, config, net
from ..models import Release
from ..ukdates import fetch_window, in_fetch_window

API = "https://www.googleapis.com/books/v1/volumes"
PAGES = 5          # up to 5 x 40 results per query (Google rarely returns more than ~150)
PAGE_SIZE = 40

# Noise: academic and reference publishers, study guides, notebooks and the like.
BLOCKED_PUBLISHERS = re.compile(
    r"university press|springer|routledge|taylor & francis|palgrave|bloomsbury academic|wiley|elsevier|"
    r"de gruyter|brill|edward elgar|peter lang|mcfarland|lexington|rowman|cambridge scholars|igi global|"
    r"crc press|emerald|sage publications|independently published|createspace", re.I)
BLOCKED_TITLES = re.compile(
    r"\b(proceedings|handbook|companion to|study guide|summary of|analysis of|workbook|notebook|journal|"
    r"colou?ring book|planner|sparknotes|cliffsnotes|anthology of criticism|box set)\b"
    # monthly ebook bundles such as "Medical Romance December 2026 Books 1-4"
    r"|\bbooks \d+\s*[-–]\s*\d+\b"
    r"|\b(january|february|march|april|may|june|july|august|september|october|november|december) 20\d\d\b",
    re.I)


def api_key() -> str:
    """From GOOGLE_BOOKS_KEY, or the file named by GOOGLE_BOOKS_KEY_FILE. Never printed."""
    key = os.environ.get("GOOGLE_BOOKS_KEY", "").strip()
    if not key and os.environ.get("GOOGLE_BOOKS_KEY_FILE"):
        key = Path(os.environ["GOOGLE_BOOKS_KEY_FILE"]).read_text(encoding="utf-8").strip()
    if not key:
        raise RuntimeError("no Google Books API key (set GOOGLE_BOOKS_KEY or GOOGLE_BOOKS_KEY_FILE)")
    return key


# Extra words that make Google return a different slice of results; each adds new books.
VARIATIONS = ("", "novel", "paperback", "hardcover", "ebook", "book 1", "series")


def queries(terms: tuple[str, ...], today: date) -> list[str]:
    start, end = fetch_window(today)
    years = sorted({start.year, end.year})
    return [f'subject:"fiction / {t}" {y} {v}'.strip() for y in years for v in VARIATIONS for t in terms]


def exact_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s and len(s) == 10 else None
    except ValueError:
        return None


def is_noise(v: dict) -> bool:
    if BLOCKED_PUBLISHERS.search(v.get("publisher") or "") or BLOCKED_TITLES.search(v.get("title") or ""):
        return True
    cats = v.get("categories") or []
    return bool(cats) and not any("fiction" in c.lower() for c in cats)


def to_release(item: dict, genre: str, today: date) -> Release | None:
    v = item.get("volumeInfo") or {}
    d = exact_date(v.get("publishedDate"))
    if not d or not in_fetch_window(d, today) or v.get("language", "en") != "en" or is_noise(v):
        return None
    isbn = next((i["identifier"] for i in v.get("industryIdentifiers", []) if i.get("type") == "ISBN_13"), None)
    if not isbn or not v.get("title") or not v.get("authors"):
        return None
    title = v["title"] + (f": {v['subtitle']}" if v.get("subtitle") and len(v["subtitle"]) < 60 else "")
    by = ", ".join(v["authors"][:2])
    img = (v.get("imageLinks") or {}).get("thumbnail")
    cover = img.replace("http://", "https://").replace("&edge=curl", "") if img else None
    return Release(kind="books", id=isbn, title=title, by=by, date=d, source="google-books",
                   amazon_url=amazon.book_url(isbn, title, by), genres=[genre], cover=cover,
                   publisher=v.get("publisher") or "", info_url=v.get("infoLink") or v.get("canonicalVolumeLink"))


def _dedupe_key(r: Release) -> tuple[str, str]:
    return re.sub(r"\W+", " ", r.title.split(":")[0]).strip().lower(), r.by.split(",")[0].strip().lower()


def merge(found: list[Release]) -> list[Release]:
    """One entry per book: combine genres, and between editions prefer a 978 ISBN, a cover, the earliest date."""
    best: dict[tuple, Release] = {}
    genres: dict[tuple, list[str]] = {}
    for r in found:
        k = _dedupe_key(r)
        genres.setdefault(k, [])
        genres[k] += [g for g in r.genres if g not in genres[k]]
        cur = best.get(k)
        if cur is None or (not cur.id.startswith("978"), cur.cover is None, cur.date) > \
                (not r.id.startswith("978"), r.cover is None, r.date):
            best[k] = r
    for k, r in best.items():
        r.genres = genres[k]
    return list(best.values())


def fetch(today: date) -> list[Release]:
    key = api_key()
    found = []
    for g in config.BOOK_GENRES:
        n = 0
        for q in queries(g.terms, today):
            for page in range(PAGES):
                url = API + "?" + urlencode({"q": q, "orderBy": "newest", "langRestrict": "en", "printType": "books",
                                             "maxResults": PAGE_SIZE, "startIndex": page * PAGE_SIZE,
                                             "country": "GB", "key": key})
                items = (net.get_json(url) or {}).get("items", [])
                for it in items:
                    r = to_release(it, g.slug, today)
                    if r:
                        found.append(r)
                        n += 1
                if not items:  # short pages happen mid-way, so only stop on an empty one
                    break
        print(f"  Google Books {g.slug}: {n} matches", file=sys.stderr)
    books = merge(found)
    print(f"  Google Books: {len(books)} books after merging editions", file=sys.stderr)
    return books
