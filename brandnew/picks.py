"""Picks of the week, chosen by hand in picks.yaml.

A pick names a book by ISBN-13 or an album by its MusicBrainz release-group ID. Details come
from the day's data when the item is in it, otherwise from Google Books or MusicBrainz, and any
field written in picks.yaml wins. A pick that can't be resolved is skipped with a warning: a typo
in picks.yaml must never stop the daily build.
"""
import copy
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urlencode

import yaml

from . import amazon, config, net
from .models import Release
from .sources import google_books as gb

MB_RELEASE_GROUP = "https://musicbrainz.org/ws/2/release-group/{}?inc=artist-credits&fmt=json"
CAA_RELEASE_GROUP = "https://coverartarchive.org/release-group/{}/front-{}"
OVERRIDES = ("title", "by", "cover")
KNOWN_KEYS = {"isbn", "mbid", "note", "from", "until", "genre", "date", *OVERRIDES}


def _warn(msg: str) -> None:
    print(f"! picks: {msg}", file=sys.stderr)


def _as_date(v) -> date | None:
    if v is None or isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v))
    except ValueError:
        return None


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = data.get("picks") or []
    if not isinstance(entries, list):
        _warn(f"{path}: 'picks' should be a list")
        return []
    return [e for e in entries if isinstance(e, dict)]


def is_active(e: dict, today: date) -> bool:
    start, until = _as_date(e.get("from")), _as_date(e.get("until"))
    if e.get("until") is None or until is None:
        _warn(f"{e.get('isbn') or e.get('mbid')}: needs an 'until' date (YYYY-MM-DD); skipped")
        return False
    return (start is None or start <= today) and today <= until


def lookup_book(isbn: str) -> Release | None:
    url = gb.API + "?" + urlencode({"q": f"isbn:{isbn}", "country": "GB", "key": gb.api_key()})
    items = (net.get_json(url) or {}).get("items") or []
    if not items:
        return None
    v = items[0].get("volumeInfo") or {}
    title, by = gb.clean_title(v.get("title") or "", v.get("subtitle")), ", ".join((v.get("authors") or [])[:2])
    img = (v.get("imageLinks") or {}).get("thumbnail")
    return Release(kind="books", id=isbn, title=title, by=by,
                   date=gb.exact_date(v.get("publishedDate")) or date.min, source="google-books",
                   amazon_url=amazon.book_url(isbn, title, by, direct=gb.is_uk_edition(v.get("publisher"))),
                   cover=img.replace("http://", "https://").replace("&edge=curl", "") if img else None,
                   publisher=v.get("publisher") or "", info_url=v.get("infoLink") or v.get("canonicalVolumeLink"))


def lookup_album(mbid: str) -> Release | None:
    d = net.get_json(MB_RELEASE_GROUP.format(mbid))
    by = "".join(c.get("name", "") + c.get("joinphrase", "") for c in d.get("artist-credit", []))
    title = d.get("title") or ""
    return Release(kind="music", id=mbid, title=title, by=by,
                   date=_as_date(d.get("first-release-date")) or date.min, source="musicbrainz",
                   amazon_url=amazon.music_url(by, title),
                   cover=CAA_RELEASE_GROUP.format(mbid, 250), cover_2x=CAA_RELEASE_GROUP.format(mbid, 500))


def resolve(entries: list[dict], releases: list[Release], today: date, lookup: bool = True) -> list[Release]:
    known = {r.id: r for r in releases}
    out = []
    for e in entries:
        if unknown := set(e) - KNOWN_KEYS:
            _warn(f"ignoring unknown field(s) {sorted(unknown)} in {e}")
        if not is_active(e, today):
            continue
        if e.get("isbn"):
            kind, id_ = "books", str(e["isbn"]).replace("-", "").replace(" ", "")
        elif e.get("mbid"):
            kind, id_ = "music", str(e["mbid"]).strip().lower()
        else:
            _warn(f"{e}: needs an 'isbn' or an 'mbid'; skipped")
            continue
        r = copy.deepcopy(known[id_]) if id_ in known else None
        if r is None and lookup:
            try:
                r = lookup_book(id_) if kind == "books" else lookup_album(id_)
            except Exception as ex:  # noqa: BLE001 - fall back to what picks.yaml says
                _warn(f"{id_}: lookup failed ({ex})")
        if r is None:
            if not (e.get("title") and e.get("by")):
                _warn(f"{id_}: not found; add 'title', 'by' and 'date' to picks.yaml to show it anyway")
                continue
            title, by = str(e["title"]), str(e["by"])
            r = Release(kind=kind, id=id_, title=title, by=by, date=date.min, source="pick",
                        amazon_url=amazon.book_url(id_, title, by, direct=False) if kind == "books"
                        else amazon.music_url(by, title))
        for k in OVERRIDES:
            if e.get(k):
                setattr(r, k, str(e[k]))
        if _as_date(e.get("date")):
            r.date = _as_date(e["date"])
        if r.date == date.min:
            _warn(f"{id_}: no release date found; add 'date' to picks.yaml")
            continue
        if e.get("genre"):
            slugs = {g.slug for g in config.genres_of(kind)}
            if e["genre"] in slugs:
                r.genres = list(dict.fromkeys([*r.genres, e["genre"]]))
            else:
                _warn(f"{id_}: unknown genre {e['genre']!r}; use one of {sorted(slugs)}")
        r.note = str(e.get("note") or "").strip()
        out.append(r)
    return out
