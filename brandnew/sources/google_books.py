"""New and upcoming books from the Google Books API.

Only queries with a year in them respect orderBy=newest, and each query stops at roughly 150
results, so every genre runs several variations of subject:"<subject>" <year> and keeps
books with an exact publication date inside the window.
"""
import os
import re
import sys
from dataclasses import replace
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
    r"colou?ring book|planner|sparknotes|cliffsnotes|anthology of criticism)\b"
    # monthly ebook bundles such as "Medical Romance December 2026"
    r"|\b(january|february|march|april|may|june|july|august|september|october|november|december) 20\d\d\b",
    re.I)
# Fiction categories: "Fiction", "Juvenile Fiction", "Young Adult Fiction", but not "Juvenile Nonfiction"
FICTION = re.compile(r"\bfiction\b", re.I)
# Repackaged series, e.g. "The Poppy Denby Investigates Boxset" subtitled "Books 1-3 in the
# series", or "Medical Romance December 2026 Books 1-4": old books, often ebook-only. Checked
# against the subtitle too, which is where "Books 1-3" often goes.
BUNDLES = re.compile(r"\bbox[- ]?sets?\b|\bbooks \d+\s*[-–]\s*\d+\b", re.I)


# Publisher marketing tacked onto titles: "Dark Waters: Now a major ITV Drama", "Die Famous: A Novel".
MARKETING = re.compile(r"now a (major|netflix)|brand[- ]new|gripping|bestsell|must[- ]read|unputdownable|addictive|"
                       r"page[- ]turner|perfect for fans|twisty|heart-?pounding|nail-?biting", re.I)
PLAIN_SUBTITLES = {"a novel", "a thriller", "a mystery", "a romance", "a novella", "novel"}
IMPRINT = re.compile(r"\s*\((mills & boon|harlequin)[^)]*\)", re.I)


# Genres that were renamed or split: data saved before the change is filed under the new slug
# until the next fresh fetch sorts it properly. "sf-fantasy" was mostly fantasy.
RENAMED_GENRES = {"sf-fantasy": "fantasy"}


def relink(releases: list[Release]) -> list[Release]:
    """Rebuild each book's Amazon link and covers and update renamed genres, so data saved by an
    older version (which linked some books straight to an ISBN page, and used small covers) works
    like fresh data."""
    out = []
    for r in releases:
        if r.kind == "books":
            genres = list(dict.fromkeys(RENAMED_GENRES.get(s, s) for s in r.genres))
            cover, cover_2x = covers(r.cover)
            r = replace(r, amazon_url=amazon.book_url(r.title, r.by), genres=genres, cover=cover, cover_2x=cover_2x)
        out.append(r)
    return out


# Cover widths offered to the browser, which picks the smallest that's sharp on its screen. Not
# 300: Google saves that one size at a higher quality, so it's bigger than 320 (68 KB against 44).
COVER_WIDTHS = (240, 320, 400, 600)


def covers(img: str | None) -> tuple[str | None, str | None]:
    """A book's cover for ordinary and sharp (2x) screens. The thumbnail Google names is only
    128 pixels wide, which looks blurred on a card; its fife=w<width> setting gives a bigger copy
    of the same image (or the biggest it has). cover_srcset() offers the in-between sizes too."""
    if not img:
        return None, None
    base = re.sub(r"&fife=w\d+", "", img.replace("http://", "https://").replace("&edge=curl", ""))
    if "books.google." not in base:
        return base, None
    return f"{base}&fife=w320", f"{base}&fife=w600"


def cover_srcset(img: str) -> str:
    """Every size in COVER_WIDTHS of a Google Books cover, for an <img srcset>."""
    base = re.sub(r"&fife=w\d+", "", img)
    return ", ".join(f"{base}&fife=w{w} {w}w" for w in COVER_WIDTHS)


def clean_title(title: str, subtitle: str | None = None) -> str:
    t = IMPRINT.sub("", title).strip()
    main, colon, rest = t.partition(":")
    if colon and (MARKETING.search(rest) or rest.strip().lower() in PLAIN_SUBTITLES):
        t = main.strip()
    if subtitle and len(subtitle) < 60 and ":" not in t and not MARKETING.search(subtitle) \
            and subtitle.strip().lower() not in PLAIN_SUBTITLES:
        t = f"{t}: {subtitle.strip()}"
    return t


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


# Google Books allows 1,000 calls a day per project and won't raise it. Each run stays well
# under that so a second run (or a local test) the same day still has room. Shared equally
# between the book genres (seven: about 64 calls each).
MAX_CALLS = 450


def query_plan(terms: tuple[str, ...], today: date) -> list[tuple[str, str]]:
    """(variation, query) pairs, most useful first."""
    start, end = fetch_window(today)
    years = sorted({start.year, end.year})
    return [(v, f'subject:"{t}" {y} {v}'.strip()) for y in years for v in VARIATIONS for t in terms]


def queries(terms: tuple[str, ...], today: date) -> list[str]:
    return [q for _, q in query_plan(terms, today)]


def exact_date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s and len(s) == 10 else None
    except ValueError:
        return None


def is_noise(v: dict) -> bool:
    title = v.get("title") or ""
    if BLOCKED_PUBLISHERS.search(v.get("publisher") or "") or BLOCKED_TITLES.search(title):
        return True
    if BUNDLES.search(f"{title} {v.get('subtitle') or ''}"):
        return True
    cats = v.get("categories") or []
    return bool(cats) and not any(FICTION.search(c) for c in cats)


def to_release(item: dict, genre: str, today: date) -> Release | None:
    v = item.get("volumeInfo") or {}
    d = exact_date(v.get("publishedDate"))
    if not d or not in_fetch_window(d, today) or v.get("language", "en") != "en" or is_noise(v):
        return None
    isbn = next((i["identifier"] for i in v.get("industryIdentifiers", []) if i.get("type") == "ISBN_13"), None)
    if not isbn or not v.get("title") or not v.get("authors"):
        return None
    title = clean_title(v["title"], v.get("subtitle"))
    by = ", ".join(v["authors"][:2])
    cover, cover_2x = covers((v.get("imageLinks") or {}).get("thumbnail"))
    return Release(kind="books", id=isbn, title=title, by=by, date=d, source="google-books",
                   amazon_url=amazon.book_url(title, by), genres=[genre], cover=cover, cover_2x=cover_2x,
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


def fetch(today: date, get_json=None) -> list[Release]:
    """Each genre gets an equal share of MAX_CALLS. A genre that fails is left empty (the pipeline
    keeps yesterday's books for it); if the daily quota runs out, what was found so far is kept."""
    get_json = get_json or net.get_json
    key = api_key()
    budget = MAX_CALLS // len(config.BOOK_GENRES)
    found: list[Release] = []
    seen: set[str] = set()
    yields: dict[str, list[int]] = {v: [0, 0] for v in VARIATIONS}  # variation -> [calls, new books]
    failed = 0
    calls = 0
    for g in config.BOOK_GENRES:
        n = used = 0
        try:
            for variation, q in query_plan(g.terms, today):
                for page in range(PAGES):
                    if used == budget:
                        break
                    url = API + "?" + urlencode({"q": q, "orderBy": "newest", "langRestrict": "en",
                                                 "printType": "books", "maxResults": PAGE_SIZE,
                                                 "startIndex": page * PAGE_SIZE, "country": "GB", "key": key})
                    used += 1
                    calls += 1
                    yields[variation][0] += 1
                    items = (get_json(url) or {}).get("items", [])
                    for it in items:
                        r = to_release(it, g.slug, today)
                        if r:
                            found.append(r)
                            n += 1
                            if r.id not in seen:
                                seen.add(r.id)
                                yields[variation][1] += 1
                    if not items:  # short pages happen mid-way, so only stop on an empty one
                        break
        except net.QuotaExhausted as e:
            print(f"! Google Books {g.slug}: {e}; stopping with what we have", file=sys.stderr)
            if not found:
                raise
            break
        except RuntimeError as e:
            failed += 1
            print(f"! Google Books {g.slug}: {e}; skipping this genre", file=sys.stderr)
            continue
        print(f"  Google Books {g.slug}: {n} matches from {used} calls", file=sys.stderr)
    if failed == len(config.BOOK_GENRES):
        raise RuntimeError("every Google Books genre failed")
    books = merge(found)
    print(f"  Google Books: {len(books)} books after merging editions, {calls} calls", file=sys.stderr)
    print("  new books per variation: " + ", ".join(
        f"{v or '(none)'} {new}/{c} calls" for v, (c, new) in yields.items() if c), file=sys.stderr)
    return books
