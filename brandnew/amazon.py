"""Amazon UK links, built without contacting Amazon (no scraping, no Amazon data).

If Amazon's Creators API is added later, it can replace these link builders.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE = "https://www.amazon.co.uk"


def isbn13_to_10(isbn13: str | None) -> str | None:
    """978-prefixed ISBN-13 -> ISBN-10. 979 ISBNs have no ISBN-10."""
    if not isbn13 or len(isbn13) != 13 or not isbn13.isdigit() or not isbn13.startswith("978"):
        return None
    core = isbn13[3:12]
    total = sum((10 - i) * int(c) for i, c in enumerate(core))
    check = (11 - total % 11) % 11
    return core + ("X" if check == 10 else str(check))


def search_url(query: str, department: str) -> str:
    return f"{BASE}/s?" + urlencode({"k": query, "i": department})


def book_url(isbn13: str | None, title: str, author: str) -> str:
    isbn10 = isbn13_to_10(isbn13)
    if isbn10:
        return f"{BASE}/dp/{isbn10}"
    return search_url(isbn13 or f"{title} {author}", "stripbooks")


def music_url(artist: str, album: str) -> str:
    return search_url(f"{artist} {album}", "popular")  # "popular" = CDs & Vinyl


def with_tag(url: str, tag: str | None) -> str:
    """Add the Associates tracking tag to an Amazon link."""
    if not tag:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "tag"] + [("tag", tag)]
    return urlunsplit(parts._replace(query=urlencode(query)))
