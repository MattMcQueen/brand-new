"""Made-up releases for local development and tests (dates are relative to today)."""
from datetime import date, timedelta

from . import amazon, config
from .models import Release


def releases(today: date) -> list[Release]:
    out = []
    offsets = (-6, -2, 0, 3, 12, 25, 40, 70)
    for g in config.BOOK_GENRES:
        for i, off in enumerate(offsets):
            isbn = f"978000000{i:03d}{ord(g.slug[0]) % 10}"
            out.append(Release(
                kind="books", id=isbn, title=f"Sample {g.name.lower()} book {i + 1}", by="A. N. Author",
                date=today + timedelta(days=off), source="sample",
                amazon_url=amazon.book_url(isbn, "", ""), genres=[g.slug], publisher="Sample Press"))
    for g in config.MUSIC_GENRES:
        for i, off in enumerate(offsets):
            artist = f"The Sample {g.name}s"
            title = f"Album {i + 1}"
            out.append(Release(
                kind="music", id=f"sample-{g.slug}-{i}", title=title, by=artist,
                date=today + timedelta(days=off), source="sample",
                amazon_url=amazon.music_url(artist, title), genres=[g.slug], tags=[g.name.lower()],
                popularity=1000 - i * 100))
    return out
