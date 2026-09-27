"""Turns release data into the static site in dist/."""
import hashlib
import json
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from itertools import count, groupby
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from markupsafe import Markup

from . import amazon, config, hosting, shops, store
from .config import Genre
from .models import Release
from .sources import google_books
from .ukdates import format_date, format_month, format_updated

STATIC = Path(__file__).parent / "static"


@dataclass
class GenrePage:
    genre: Genre
    past: list[Release]
    past_days: int                             # 7, or 14 when the last week was empty
    upcoming: list[tuple[str, list[Release]]]  # (month name, releases)

    @property
    def url(self) -> str:
        return genre_url(self.genre)

    @property
    def count(self) -> int:
        return len(self.past) + sum(len(rs) for _, rs in self.upcoming)
    covers: list[Release] = field(default_factory=list)  # for the genre's tile: see pick_tile_covers


def genre_url(g: Genre) -> str:
    return f"/{g.kind}/{g.slug}/"


def _past_key(r: Release):
    return (-r.popularity, -r.date.toordinal(), r.title.lower())


def _upcoming_key(r: Release):
    return (r.date, -r.popularity, r.title.lower())


@dataclass
class Recent:
    releases: list[Release]
    days: int                                  # 7, or 14 when the last week was empty


def recent(releases: list[Release], today: date) -> Recent:
    """What came out in the last week, or the last two weeks if that's empty, most popular first."""
    for days in (config.PAST_DAYS, config.PAST_FALLBACK_DAYS):
        past = [r for r in releases if today - timedelta(days=days) <= r.date <= today]
        if past:
            break
    return Recent(sorted(past, key=_past_key), days)


def genre_page(genre: Genre, releases: list[Release], today: date) -> GenrePage:
    mine = [r for r in releases if r.kind == genre.kind and genre.slug in r.genres]
    got = recent(mine, today)
    past, past_days = got.releases, got.days
    upcoming = sorted((r for r in mine if today < r.date <= today + timedelta(days=config.UPCOMING_DAYS)),
                      key=_upcoming_key)
    months = [(format_month(d), list(rs)) for d, rs in groupby(upcoming, key=lambda r: r.date.replace(day=1))]
    return GenrePage(genre, past, past_days, months)


COVER_HUES = 8


def cover_hue(r: Release) -> int:
    """Which colour scheme a release's made-up cover uses: fixed per release, so it looks the same every day."""
    return int(hashlib.sha1(r.id.encode()).hexdigest()[:8], 16) % COVER_HUES


def cover_srcset(r: Release) -> str | None:
    """The sizes of a cover the browser can choose from (the <img sizes> says how wide it's shown):
    a Google Books cover comes in any width, a Cover Art Archive one in 250 and 500 pixels."""
    if not r.cover_2x:
        return None
    if "books.google." in r.cover:
        return google_books.cover_srcset(r.cover)
    return f"{r.cover} 250w, {r.cover_2x} 500w"


def countdown(d: date, today: date) -> str | None:
    """The sticker on a release's cover, if it's close to its release date."""
    days = (d - today).days
    if days == 0:
        return "Out today!"
    if days == 1:
        return "Out tomorrow"
    if 2 <= days <= 7:
        return f"{days} days to go"
    if -2 <= days < 0:
        return "Just out"
    return None


def pick_tile_covers(pages: list[GenrePage], per_tile: int = 3, spares: int = 2) -> None:
    """Give each genre's tile `per_tile` covers: what's just out first, then what's next.
    A release in several genres would otherwise front every one of their tiles, so covers already
    used by an earlier tile are only taken when a genre has nothing else.
    Each tile also gets up to `spares` more, hidden (style.css): the cover hosts sometimes fail,
    app.js removes a cover that does, and the next one moves up so the fan stays full."""
    used = set()
    for p in pages:
        shown = [r for r in p.past + [r for _, rs in p.upcoming for r in rs] if r.cover]
        fresh = [r for r in shown if r.id not in used]
        p.covers = (fresh + [r for r in shown if r.id in used])[:per_tile + spares]
        used.update(r.id for r in p.covers[:per_tile])


def lower_name(name: str) -> str:
    """Lower-case a genre name for use mid-sentence, keeping acronyms: "Tech & AI" -> "tech & AI"."""
    return " ".join(w if len(w) > 1 and w.isupper() else w.lower() for w in name.split())


def names(shops_: Iterable) -> str:
    """Shop names as a list in a sentence: "A, B and C"."""
    n = [s.name for s in shops_]
    return " and ".join(filter(None, [", ".join(n[:-1]), n[-1]])) if n else ""


def logo_svg() -> str:
    """The favicon, inline in the header, so the two can never drift apart."""
    svg = (STATIC / "favicon.svg").read_text(encoding="utf-8").strip()
    return svg.replace('<svg xmlns="http://www.w3.org/2000/svg" ',
                       '<svg class="logo-mark" width="44" height="44" aria-hidden="true" focusable="false" ', 1)


def asset_url(name: str) -> str:
    """/static/<name> with a fingerprint of its contents, so browsers fetch it again when it changes."""
    digest = hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:8]
    return f"/static/{name}?v={digest}"


# Structured data (schema.org JSON-LD), so search engines can tell what's on each page.
# Only the breadcrumbs can show up in Google's results; the rest helps it understand the pages.

def json_ld(data) -> Markup:
    """`data` as JSON for a <script type="application/ld+json">. <, > and & are escaped, so a
    title containing "</script>" can't end the block early."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return Markup(text.replace("<", r"\u003c").replace(">", r"\u003e").replace("&", r"\u0026"))


def _breadcrumbs(*trail: tuple[str, str]) -> dict:
    return {"@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [{"@type": "ListItem", "position": i, "name": name, "item": config.SITE_URL + path}
                                for i, (name, path) in enumerate(trail, 1)]}


def _release_ld(r: Release, genre: Genre) -> dict:
    item = {"name": r.title, "datePublished": r.date.isoformat(), "genre": genre.name}
    if r.kind == "books":
        # Google Books authors are joined with ", " (see sources/google_books.py)
        item |= {"@type": "Book", "isbn": r.id,
                 "author": [{"@type": "Person", "name": a} for a in r.by.split(", ") if a]}
        if r.info_url:
            item["url"] = r.info_url
    else:
        item |= {"@type": "MusicAlbum", "byArtist": {"@type": "MusicGroup", "name": r.by},
                 "url": f"https://musicbrainz.org/release-group/{r.id}"}
    if r.cover:
        item["image"] = r.cover
    return item


def website_ld() -> dict:
    return {"@context": "https://schema.org", "@type": "WebSite", "name": config.SITE_NAME, "url": config.SITE_URL + "/"}


def kind_ld(kind: str) -> list[dict]:
    return [_breadcrumbs((config.SITE_NAME, "/"), (config.KIND_NAMES[kind], f"/{kind}/"))]


def genre_ld(page: GenrePage) -> list[dict]:
    """The page as a list of the releases on it (in page order), plus its breadcrumbs."""
    shown = page.past + [r for _, rs in page.upcoming for r in rs]
    g = page.genre
    collection = {
        "@context": "https://schema.org", "@type": "CollectionPage", "url": config.SITE_URL + page.url,
        "name": f"New {lower_name(g.name)} {'books' if g.kind == 'books' else 'albums'}",
        "mainEntity": {"@type": "ItemList", "numberOfItems": len(shown),
                       "itemListElement": [{"@type": "ListItem", "position": i, "item": _release_ld(r, g)}
                                           for i, r in enumerate(shown, 1)]},
    }
    return [collection, _breadcrumbs((config.SITE_NAME, "/"), (config.KIND_NAMES[g.kind], f"/{g.kind}/"),
                                     (g.name, page.url))]


@dataclass(frozen=True)
class Trial:
    """A trial affiliate line under one of the pop-up's groups of links, also offered on the About page."""
    group: str   # the heading of the pop-up group it goes under
    name: str
    intro: str
    link: str
    url: str
    about: str   # what it is, for the About page's list


def trials(amazon_tag: str | None) -> list[Trial]:
    """The trial lines, in the order the About page lists them. None without a tag: they
    couldn't earn anything."""
    if not amazon_tag:
        return []
    return [
        Trial("Ebooks & audiobooks", "Kindle Unlimited", "Some books are free to read with Kindle Unlimited.",
              "Try it free for 30 days", amazon.with_tag(amazon.KINDLE_UNLIMITED_URL, amazon_tag),
              "ebooks, with some audiobooks and magazines, free for 30 days."),
        # No "free" or trial length: Audible's offer changes with its promotions.
        Trial("Ebooks & audiobooks", "Audible", "Audible gives you an audiobook a month.",
              "Try Audible", amazon.with_tag(amazon.AUDIBLE_URL, amazon_tag),
              "an audiobook a month, with an offer for new members."),
        Trial("Listen", "Amazon Music Unlimited", "Amazon Music Unlimited has every new release.",
              "Try it free", amazon.with_tag(amazon.MUSIC_UNLIMITED_URL, amazon_tag),
              "ad-free music, including every new release."),
    ]


def _env(amazon_tag: str | None) -> Environment:
    env = Environment(loader=PackageLoader("brandnew", "templates"),
                      autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["uk_date"] = format_date
    env.filters["lower_name"] = lower_name
    env.filters["names"] = names
    env.filters["json_ld"] = json_ld
    env.filters["amazon"] = lambda url: amazon.with_tag(url, amazon_tag)
    ids = count(1)
    env.globals.update(config=config, genre_url=genre_url, countdown=countdown, cover_hue=cover_hue, cover_srcset=cover_srcset, asset=asset_url, logo_svg=logo_svg(), kind_names=config.KIND_NAMES,
                       other_shops=lambda r, today: shops.groups_for(
                           r.kind, r.title, r.by,
                           out_on=format_date(r.date) if r.kind == "music" and r.date > today else ""),
                       amazon_kindle=lambda r: amazon.kindle_url(r.title, r.by),
                       amazon_audible=lambda r: amazon.audible_url(r.title, r.by),
                       trials=trials(amazon_tag),
                       bookshops=shops.BOOKSHOPS, digital_shops=shops.DIGITAL_SHOPS, record_shops=shops.RECORD_SHOPS,
                       streaming=shops.STREAMING, next_id=lambda: next(ids))  # unique element ids (a book can be on a page twice)
    return env


def build(releases: list[Release], generated: datetime, out: Path, today: date,
          amazon_tag: str | None = None) -> list[str]:
    """Write the whole site to `out`. Returns the page paths written."""
    # Empty `out` rather than deleting it: a running preview (e.g. Docker) keeps a hold on the
    # folder itself and would go on serving the old files if it were replaced.
    out.mkdir(parents=True, exist_ok=True)
    for child in out.iterdir():
        shutil.rmtree(child) if child.is_dir() else child.unlink()
    env = _env(amazon_tag)
    pages = {g.slug + g.kind: genre_page(g, releases, today) for g in config.ALL_GENRES}
    for kind in ("books", "music"):
        pick_tile_covers([pages[g.slug + g.kind] for g in config.genres_of(kind)])
    common = dict(today=today, updated=format_updated(generated), generated_iso=generated.isoformat(), pages=pages,
                  book_pages=[pages[g.slug + g.kind] for g in config.BOOK_GENRES],
                  music_pages=[pages[g.slug + g.kind] for g in config.MUSIC_GENRES])
    written = []

    def write(path: str, template: str, **ctx):
        target = out / path.lstrip("/")
        if path.endswith("/"):
            target = target / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(env.get_template(template).render(path=path, **common, **ctx), encoding="utf-8")
        written.append(path)

    write("/", "home.html", ld=website_ld())
    for kind in ("books", "music"):
        # every release of the kind appears once, even when it's in several genres
        unique = list({r.id: r for r in reversed(releases) if r.kind == kind}.values())
        write(f"/{kind}/", "kind.html", kind=kind, ld=kind_ld(kind), recent=recent(unique, today),
              pages_of_kind=[pages[g.slug + g.kind] for g in config.genres_of(kind)])
    for p in pages.values():
        siblings = [pages[g.slug + g.kind] for g in config.genres_of(p.genre.kind)]
        write(p.url, "genre.html", page=p, siblings=siblings, ld=genre_ld(p))
    write("/about/", "about.html")
    write("/404.html", "404.html")

    shutil.copytree(STATIC, out / "static")
    (out / "staticwebapp.config.json").write_text(json.dumps(hosting.config(), indent=2) + "\n", encoding="utf-8")
    store.save(out / "data" / "releases.json", releases, generated)
    (out / ".well-known").mkdir()
    (out / ".well-known" / "atproto-did").write_text(config.BLUESKY_DID, encoding="utf-8")
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n",
                                    encoding="utf-8")
    # Every page but About changes with each morning's data. About gets no <lastmod>: search engines
    # stop trusting the dates if they claim changes that didn't happen.
    lastmod = f"<lastmod>{generated.date().isoformat()}</lastmod>"
    urls = "".join(f"<url><loc>{config.SITE_URL}{p}</loc>{'' if p == '/about/' else lastmod}</url>"
                   for p in written if p.endswith("/"))
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    return written
