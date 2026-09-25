"""Turns release data into the static site in dist/."""
import hashlib
import shutil
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import count, groupby
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from . import amazon, config, shops, store
from .config import Genre
from .models import Release
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


def genre_url(g: Genre) -> str:
    return f"/{g.kind}/{g.slug}/"


def _past_key(r: Release):
    return (-r.popularity, -r.date.toordinal(), r.title.lower())


def _upcoming_key(r: Release):
    return (r.date, -r.popularity, r.title.lower())


def genre_page(genre: Genre, releases: list[Release], today: date) -> GenrePage:
    mine = [r for r in releases if r.kind == genre.kind and genre.slug in r.genres]
    past_days = config.PAST_DAYS
    past = [r for r in mine if today - timedelta(days=past_days) <= r.date <= today]
    if not past:
        past_days = config.PAST_FALLBACK_DAYS
        past = [r for r in mine if today - timedelta(days=past_days) <= r.date <= today]
    upcoming = sorted((r for r in mine if today < r.date <= today + timedelta(days=config.UPCOMING_DAYS)),
                      key=_upcoming_key)
    months = [(format_month(d), list(rs)) for d, rs in groupby(upcoming, key=lambda r: r.date.replace(day=1))]
    return GenrePage(genre, sorted(past, key=_past_key), past_days, months)


def logo_svg() -> str:
    """The favicon, inline in the header, so the two can never drift apart."""
    svg = (STATIC / "favicon.svg").read_text(encoding="utf-8").strip()
    return svg.replace('<svg xmlns="http://www.w3.org/2000/svg" ',
                       '<svg class="logo-mark" width="30" height="30" aria-hidden="true" focusable="false" ', 1)


def asset_url(name: str) -> str:
    """/static/<name> with a fingerprint of its contents, so browsers fetch it again when it changes."""
    digest = hashlib.sha256((STATIC / name).read_bytes()).hexdigest()[:8]
    return f"/static/{name}?v={digest}"


def _env(amazon_tag: str | None) -> Environment:
    env = Environment(loader=PackageLoader("brandnew", "templates"),
                      autoescape=select_autoescape(["html", "xml"]),
                      trim_blocks=True, lstrip_blocks=True)
    env.filters["uk_date"] = format_date
    env.filters["amazon"] = lambda url: amazon.with_tag(url, amazon_tag)
    ids = count(1)
    env.globals.update(config=config, genre_url=genre_url, asset=asset_url, logo_svg=logo_svg(), kind_names=config.KIND_NAMES,
                       other_shops=lambda r: shops.groups_for(r.kind, r.id, r.title, r.by, r.uk_edition),
                       amazon_kindle=lambda r: amazon.kindle_url(r.title, r.by),
                       amazon_audible=lambda r: amazon.audible_url(r.title, r.by),
                       bookshops=shops.BOOKSHOPS, digital_shops=shops.DIGITAL_SHOPS, record_shops=shops.RECORD_SHOPS, next_id=lambda: next(ids))  # unique element ids (a book can be on a page twice)
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
    common = dict(updated=format_updated(generated), pages=pages,
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

    write("/", "home.html")
    for p in pages.values():
        siblings = [pages[g.slug + g.kind] for g in config.genres_of(p.genre.kind)]
        write(p.url, "genre.html", page=p, siblings=siblings)
    write("/about/", "about.html")
    write("/404.html", "404.html")

    shutil.copytree(STATIC, out / "static")
    store.save(out / "data" / "releases.json", releases, generated)
    (out / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {config.SITE_URL}/sitemap.xml\n",
                                    encoding="utf-8")
    urls = "".join(f"<url><loc>{config.SITE_URL}{p}</loc></url>" for p in written if p.endswith("/"))
    (out / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n', encoding="utf-8")
    return written
