"""Albums from the ListenBrainz fresh-releases feed, ranked by artist popularity,
with genres from MusicBrainz artist lookups (cached between runs)."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .. import amazon, config, net
from ..models import Release
from ..ukdates import in_fetch_window

FEED_URL = "https://api.listenbrainz.org/1/explore/fresh-releases/?days=90&past=true&future=true"
POPULARITY_URL = "https://api.listenbrainz.org/1/popularity/artist"
ARTIST_URL = "https://musicbrainz.org/ws/2/artist/{}?inc=genres+tags&fmt=json"
COVER_URL = "https://coverartarchive.org/release/{}/{}-{}.jpg"

# Secondary types that aren't new studio albums (soundtracks and mixtapes stay).
EXCLUDED_SECONDARY = {"Compilation", "Live", "Remix", "Demo", "DJ-mix", "Spokenword", "Audio drama",
                      "Interview", "Audiobook", "Field recording"}
NOT_NEW = re.compile(r"\b(remaster(ed)?|reissue|anniversary|expanded edition|live (at|in|from))\b", re.I)
ARTIST_GENRES_USED = 3  # an artist's top genres only; further down the list is too loose
EDITION_SUFFIX = re.compile(r"\s*([\(\[].*|\s-\s.*(edition|version|deluxe).*)$", re.I)

MIN_LISTENERS = 200     # artists with fewer ListenBrainz listeners are left out
MAX_CANDIDATES = 500    # most popular albums to look up genres for
MAX_PER_GENRE = 60      # per genre page
GENRE_CACHE_DAYS = 30
MAX_LOOKUPS = 700       # MusicBrainz lookups per run (~13 minutes at 1 per second)
COVER_TRIES = 3         # the Cover Art Archive sends each request to one of a cover's copies; some can be broken
COVER_WORKERS = 8       # covers looked up at once (about 2 minutes for 300 albums)


def base_title(title: str) -> str:
    """'Album (Deluxe Edition)' -> 'album', used to spot several editions of one album."""
    return EDITION_SUFFIX.sub("", title or "").strip().lower()


def albums_from_feed(releases: list[dict], today: date) -> list[dict]:
    """Keep albums with an exact date in the window; one entry per album."""
    best: dict[tuple, dict] = {}
    for r in releases:
        if r.get("release_group_primary_type") != "Album" or not r.get("artist_mbids"):
            continue
        if r.get("release_group_secondary_type") in EXCLUDED_SECONDARY or NOT_NEW.search(r.get("release_name") or ""):
            continue
        try:
            d = date.fromisoformat(r.get("release_date") or "")
        except ValueError:
            continue  # partial dates such as "2026" or "2026-10"
        if not in_fetch_window(d, today):
            continue
        key = ((r.get("artist_credit_name") or "").lower(), base_title(r.get("release_name")))
        cand = dict(r, date=d)
        cur = best.get(key)
        # Prefer the entry with a cover, then the earliest date, then the plainest title
        if cur is None or (not cur.get("caa_id"), cur["date"], len(cur["release_name"])) > \
                (not r.get("caa_id"), d, len(r["release_name"])):
            best[key] = cand
    return list(best.values())


def match_genres(tags: list[str]) -> list[str]:
    text = " | ".join(tags).lower()
    return [g.slug for g in config.MUSIC_GENRES
            if any(re.search(rf"\b{re.escape(t)}\b", text) for t in g.terms)]


def fetch_popularity(mbids: list[str]) -> dict[str, int]:
    pop = {}
    for i in range(0, len(mbids), 200):
        for row in net.get_json(POPULARITY_URL, data={"artist_mbids": mbids[i:i + 200]}) or []:
            if row.get("artist_mbid"):
                pop[row["artist_mbid"]] = row.get("total_user_count") or 0
    return pop


def artist_genres(mbid: str) -> list[str]:
    d = net.get_json(ARTIST_URL.format(mbid))
    genres = [x["name"] for x in sorted(d.get("genres", []), key=lambda x: -x.get("count", 0))]
    tags = [x["name"] for x in sorted(d.get("tags", []), key=lambda x: -x.get("count", 0))]
    return (genres or tags)[:10]


class GenreCache:
    """Artist genres, kept between runs so we only ask MusicBrainz about new artists."""

    def __init__(self, path: Path, today: date):
        self.path, self.today = path, today
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def get(self, mbid: str) -> list[str] | None:
        e = self.data.get(mbid)
        if e and date.fromisoformat(e["checked"]) > self.today - timedelta(days=GENRE_CACHE_DAYS):
            return e["genres"]
        return None

    def put(self, mbid: str, genres: list[str]) -> None:
        self.data[mbid] = {"genres": genres, "checked": self.today.isoformat()}

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, ensure_ascii=False), encoding="utf-8")


def to_release(a: dict, artist_tags: list[str], popularity: int) -> Release | None:
    tags = list(dict.fromkeys(t.lower() for t in (a.get("release_tags") or []) + artist_tags[:ARTIST_GENRES_USED]))
    genres = match_genres(tags)
    if not genres:
        return None
    by, title = a.get("artist_credit_name") or "", a.get("release_name") or ""
    cover = cover_2x = None
    if a.get("caa_id") and a.get("caa_release_mbid"):
        cover = COVER_URL.format(a["caa_release_mbid"], a["caa_id"], 250)
        cover_2x = COVER_URL.format(a["caa_release_mbid"], a["caa_id"], 500)
    return Release(kind="music", id=a["release_group_mbid"], title=title, by=by, date=a["date"],
                   source="listenbrainz", amazon_url=amazon.music_url(by, title), genres=genres,
                   tags=tags[:3], cover=cover, cover_2x=cover_2x, popularity=popularity)


def cap_per_genre(releases: list[Release], limit: int = MAX_PER_GENRE) -> list[Release]:
    """Keep each genre's most popular `limit` albums; drop albums left with no genre."""
    keep: dict[str, set[str]] = {}
    for g in config.MUSIC_GENRES:
        mine = sorted((r for r in releases if g.slug in r.genres), key=lambda r: -r.popularity)
        for r in mine[:limit]:
            keep.setdefault(r.id, set()).add(g.slug)
    out = []
    for r in releases:
        if r.id in keep:
            r.genres = [s for s in r.genres if s in keep[r.id]]
            out.append(r)
    return out


def fetch(today: date, cache_path: Path) -> list[Release]:
    feed = net.get_json(FEED_URL)
    raw = (feed.get("payload") or feed).get("releases", [])
    albums = albums_from_feed(raw, today)
    artists = sorted({a["artist_mbids"][0] for a in albums})
    pop = fetch_popularity(artists)
    ranked = sorted((a for a in albums if pop.get(a["artist_mbids"][0], 0) >= MIN_LISTENERS),
                    key=lambda a: -pop[a["artist_mbids"][0]])[:MAX_CANDIDATES]
    print(f"  ListenBrainz: {len(raw)} releases, {len(albums)} albums in window, "
          f"{len(ranked)} by artists with {MIN_LISTENERS}+ listeners", file=sys.stderr)

    cache = GenreCache(cache_path, today)
    lookups = 0
    out = []
    try:
        for a in ranked:
            aid = a["artist_mbids"][0]
            tags = cache.get(aid)
            if tags is None:
                if lookups >= MAX_LOOKUPS:
                    continue
                lookups += 1
                try:
                    tags = artist_genres(aid)
                except RuntimeError as e:
                    print(f"  ! {e}", file=sys.stderr)
                    continue
                cache.put(aid, tags)
                if lookups % 50 == 0:
                    cache.save()
            r = to_release(a, tags, pop[aid])
            if r:
                out.append(r)
    finally:
        cache.save()
    print(f"  MusicBrainz: {lookups} artist lookups, {len(out)} albums matched a genre", file=sys.stderr)
    return cap_per_genre(out)


def direct_covers(releases: list[Release]) -> list[Release]:
    """Link album covers straight to the Internet Archive server that holds them. A Cover Art
    Archive link goes through two redirects first (coverartarchive.org, then archive.org), each a
    new connection to a server in North America, which made album covers much slower to appear
    than book covers. Following them here, once a day, also steps around copies that are broken
    today. Nothing is copied: the covers stay on the Internet Archive. The Cover Art Archive link
    is kept as the backup early.js falls back on, and stays the cover if no working copy is found."""
    todo = [i for i, r in enumerate(releases)
            if r.kind == "music" and r.cover and r.cover.startswith("https://coverartarchive.org/")]

    def direct(r: Release) -> Release:
        for _ in range(COVER_TRIES):
            url = net.final_url(r.cover)
            host = urlsplit(url or "").hostname or ""
            if host.endswith(".archive.org") and url.endswith("_thumb250.jpg"):
                return replace(r, cover=url, cover_2x=url.removesuffix("250.jpg") + "500.jpg", cover_backup=r.cover)
        return r

    out = list(releases)
    with ThreadPoolExecutor(COVER_WORKERS) as pool:
        for i, r in zip(todo, pool.map(direct, [releases[i] for i in todo])):
            out[i] = r
    found = sum(out[i].cover_backup is not None for i in todo)
    print(f"  Covers: {found} of {len(todo)} albums linked straight to the Internet Archive", file=sys.stderr)
    return out
