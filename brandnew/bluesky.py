"""The weekly Bluesky thread: what came out this week, one reply per genre.

`thread()` only writes the posts; `post_thread()` sends them. Links go to our own pages (never
straight to Amazon), shown as link cards with the site's share image.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import config, net
from .config import Genre
from .models import Release
from .render import genre_url, lower_name
from .ukdates import UK

LIMIT = 300               # Bluesky's limit, in characters as people see them
HIGHLIGHTS = 4            # titles named per genre, at most
DAYS = 7                  # Saturday to Friday: each release is in exactly one week's thread
OPENING = "Out this week on Brand New"  # how the "already posted today?" check spots our thread
PDS = "https://bsky.social"
PUBLIC_API = "https://public.api.bsky.app"
SHARE_IMAGE = Path(__file__).parent / "static" / "share.png"
UTM = "?utm_source=bluesky&utm_medium=social&utm_campaign=weekly"

KIND_TAGS = {"books": "BookSky", "music": "NewMusicFriday"}
GENRE_TAGS = {
    "crime-thrillers": "CrimeFiction", "childrens": "KidLit", "romance": "Romance", "fantasy": "Fantasy",
    "literary-fiction": "LitFic", "historical-fiction": "HistFic", "science-fiction": "SciFi",
    "horror": "Horror",
    "rock": "Rock", "pop": "Pop", "hip-hop": "HipHop", "rnb-soul": "RnB", "electronic": "ElectronicMusic",
    "indie": "IndieMusic", "metal": "Metal", "country": "CountryMusic", "folk": "FolkMusic", "jazz": "Jazz",
}
NOUNS = {"books": ("book", "books"), "music": ("album", "albums")}


@dataclass
class Card:
    url: str
    title: str
    description: str


@dataclass
class Post:
    text: str
    card: Card
    tags: list[str] = field(default_factory=list)  # hashtags at the end of the text, without the #


def this_week(releases: list[Release], today: date) -> list[Release]:
    return [r for r in releases if today - timedelta(days=DAYS - 1) <= r.date <= today]


def _count(n: int, kind: str) -> str:
    one, many = NOUNS[kind]
    return f"{n} new {one if n == 1 else many}"


def _highlight_key(r: Release):
    # Music: most listened first. Books have no popularity, so ones with a cover, then the newest.
    return (-r.popularity, r.cover is None, -r.date.toordinal(), r.title.lower())


def short_title(r: Release) -> str:
    """Books without the subtitle or series: 'Incarnate', not 'Incarnate: A Novel (Book 1)'.
    The same cut as the shop searches make (shops.py). Album titles are left alone."""
    if r.kind != "books":
        return r.title
    short = re.sub(r"\s*\([^)]*\)\s*$", "", r.title.split(":")[0]).strip()
    return short or r.title


def _with_tags(body: str, tags: list[str]) -> str:
    return f"{body}\n\n{' '.join('#' + t for t in tags)}" if tags else body


def _fit(head: str, releases: list[Release], tags: list[str]) -> str:
    """'Fantasy, 8 new books: A by X; B by Y; and 6 more', with as many titles as fit."""
    names = [f"{short_title(r)} by {r.by}" for r in releases]
    for n in range(min(len(names), HIGHLIGHTS), 0, -1):
        rest = len(names) - n
        body = f"{head}: {'; '.join(names[:n])}" + (f"; and {rest} more" if rest else "")
        if len(_with_tags(body, tags)) <= LIMIT:
            return _with_tags(body, tags)
    # Even one title is too long: shorten it.
    more = f"; and {len(names) - 1} more" if len(names) > 1 else ""
    room = LIMIT - len(_with_tags(f"{head}: {more}", tags)) - 1
    return _with_tags(f"{head}: {names[0][:room].rstrip()}…{more}", tags)


def genre_post(genre: Genre, releases: list[Release]) -> Post:
    tags = [GENRE_TAGS[genre.slug], KIND_TAGS[genre.kind]]
    head = f"{genre.name}, {_count(len(releases), genre.kind)}"
    noun = NOUNS[genre.kind][1]
    card = Card(config.SITE_URL + genre_url(genre) + UTM,
                f"New {lower_name(genre.name)} {noun}: out now and coming soon",
                genre.blurb or f"New {lower_name(genre.name)} {noun}, out this week and coming soon.")
    return Post(_fit(head, sorted(releases, key=_highlight_key), tags), card, tags)


def thread(releases: list[Release], today: date) -> list[Post]:
    """The opening post, then a reply for each genre with something out this week, in site order."""
    week = this_week(releases, today)
    counts = [_count(sum(r.kind == kind for r in week), kind)
              for kind in ("books", "music") if any(r.kind == kind for r in week)]
    if not counts:
        return []
    tags = [KIND_TAGS[k] for k in ("books", "music") if any(r.kind == k for r in week)]
    opening = Post(
        _with_tags(f"{OPENING}: {' and '.join(counts)}, sorted by genre. Highlights below 🧵", tags),
        Card(config.SITE_URL + "/" + UTM, f"{config.SITE_NAME}: new and upcoming books and music",
             "New and upcoming books and albums, by genre: what came out this week and what's coming soon."),
        tags)
    replies = []
    for g in config.ALL_GENRES:
        mine = [r for r in week if r.kind == g.kind and g.slug in r.genres]
        if mine:
            replies.append(genre_post(g, mine))
    return [opening] + replies


def preview(posts: list[Post]) -> str:
    """The thread as plain text, for a dry run."""
    out = []
    for i, p in enumerate(posts, 1):
        out.append(f"--- {i}/{len(posts)} ({len(p.text)}/{LIMIT} characters) ---\n{p.text}\n"
                   f"[card: {p.card.title} -> {p.card.url}]")
    return "\n\n".join(out)


def facets(text: str, tags: list[str]) -> list[dict]:
    """Makes the hashtags clickable. Bluesky counts positions in UTF-8 bytes, not characters."""
    data = text.encode("utf-8")
    out, start = [], 0
    for tag in tags:
        needle = f"#{tag}".encode("utf-8")
        at = data.find(needle, start)
        if at < 0:
            continue
        out.append({"index": {"byteStart": at, "byteEnd": at + len(needle)},
                    "features": [{"$type": "app.bsky.richtext.facet#tag", "tag": tag}]})
        start = at + len(needle)
    return out


# --- Sending --------------------------------------------------------------------------------

Http = Callable[[str, str, bytes | None, dict], dict]  # (method, url, body, headers) -> JSON


def _http(method: str, url: str, body: bytes | None, headers: dict) -> dict:
    """One attempt, no retries: a retried post could appear twice."""
    req = urllib.request.Request(url, data=body, method=method,
                                 headers={"User-Agent": config.USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise RuntimeError(f"Bluesky said {e.code} to {url.rsplit('/', 1)[-1]}: {detail}") from None


class Client:
    def __init__(self, handle: str, app_password: str, http: Http = _http):
        self.http = http
        s = http("POST", f"{PDS}/xrpc/com.atproto.server.createSession",
                 json.dumps({"identifier": handle, "password": app_password}).encode(),
                 {"Content-Type": "application/json"})
        self.did, self.handle = s["did"], s["handle"]
        self.auth = {"Authorization": f"Bearer {s['accessJwt']}"}

    def upload(self, data: bytes, mime: str) -> dict:
        return self.http("POST", f"{PDS}/xrpc/com.atproto.repo.uploadBlob", data,
                         {**self.auth, "Content-Type": mime})["blob"]

    def create(self, record: dict) -> dict:
        body = {"repo": self.did, "collection": "app.bsky.feed.post", "record": record}
        return self.http("POST", f"{PDS}/xrpc/com.atproto.repo.createRecord", json.dumps(body).encode(),
                         {**self.auth, "Content-Type": "application/json"})

    def post_url(self, uri: str) -> str:
        return f"https://bsky.app/profile/{self.handle}/post/{uri.rsplit('/', 1)[-1]}"


def record(post: Post, thumb: dict | None, now: datetime, reply: dict | None = None) -> dict:
    external = {"uri": post.card.url, "title": post.card.title, "description": post.card.description}
    if thumb:
        external["thumb"] = thumb
    rec = {"$type": "app.bsky.feed.post", "text": post.text, "langs": ["en-GB"],
           "createdAt": now.astimezone(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
           "facets": facets(post.text, post.tags),
           "embed": {"$type": "app.bsky.embed.external", "external": external}}
    if reply:
        rec["reply"] = reply
    return rec


def posted_today(handle: str, today: date, get_json=net.get_json) -> bool:
    """Is this week's thread already on the account? Read from Bluesky's public API, so a re-run
    of the workflow can't post it twice."""
    feed = get_json(f"{PUBLIC_API}/xrpc/app.bsky.feed.getAuthorFeed?actor={handle}"
                    "&filter=posts_no_replies&limit=20")["feed"]
    for item in feed:
        rec = item["post"]["record"]
        when = datetime.fromisoformat(rec["createdAt"].replace("Z", "+00:00")).astimezone(UK).date()
        if when == today and rec.get("text", "").startswith(OPENING):
            return True
    return False


def post_thread(posts: list[Post], client: Client, now: datetime) -> list[str]:
    """Posts the thread and returns the links to each post. If one fails, the error lists what
    did get posted, so the rest can be tidied up by hand."""
    thumb = client.upload(SHARE_IMAGE.read_bytes(), "image/png")
    done: list[str] = []
    root = parent = None
    try:
        for p in posts:
            reply = {"root": root, "parent": parent} if root else None
            made = client.create(record(p, thumb, now, reply))
            parent = {"uri": made["uri"], "cid": made["cid"]}
            root = root or parent
            done.append(client.post_url(made["uri"]))
    except Exception as e:
        posted = "\n".join(done) or "nothing"
        raise RuntimeError(f"{e}\nPosted {len(done)} of {len(posts)}:\n{posted}") from None
    print(f"Posted {len(done)} posts: {done[0]}", file=sys.stderr)
    return done
