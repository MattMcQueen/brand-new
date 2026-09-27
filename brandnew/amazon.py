"""Amazon UK links, built without contacting Amazon (no scraping, no Amazon data).

If Amazon's Creators API is added later, it can replace these link builders.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE = "https://www.amazon.co.uk"
# Associates' landing page for an Amazon Music Unlimited free trial, which pays a fixed fee per
# trial started from it (Prime members included). Amazon redirects it to /music/unlimited, tag kept.
MUSIC_UNLIMITED_URL = f"{BASE}/unlimited"
# The same for a 30-day Kindle Unlimited free trial. Amazon redirects it to its sign-up page, tag kept.
KINDLE_UNLIMITED_URL = f"{BASE}/kindle-dbs/hz/signup"


def search_url(query: str, department: str) -> str:
    return f"{BASE}/s?" + urlencode({"k": query, "i": department})


def book_url(title: str, author: str) -> str:
    """A title + author search, never a /dp/ page: Google Books often lists the ebook edition,
    whose ISBN has no Amazon page (Kindle books go by Amazon's own IDs), and we can't check which
    ISBNs Amazon has without contacting it. The search finds whichever editions Amazon UK sells."""
    return search_url(_short_query(title, author), "stripbooks")


def _short_query(title: str, author: str) -> str:
    return f"{title.split(':')[0].strip()} {author.split(',')[0].strip()}"


def kindle_url(title: str, author: str) -> str:
    """A Kindle Store search: the ebook has its own ASIN, so we can't link to it directly."""
    return search_url(_short_query(title, author), "digital-text")


def audible_url(title: str, author: str) -> str:
    """An Audible search on Amazon UK. Not every book has an audiobook, so this is always a search."""
    return search_url(_short_query(title, author), "audible")


def music_url(artist: str, album: str) -> str:
    return search_url(f"{artist} {album}", "popular")  # "popular" = CDs & Vinyl


def with_tag(url: str, tag: str | None) -> str:
    """Add the Associates tracking tag to an Amazon link."""
    if not tag:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != "tag"] + [("tag", tag)]
    return urlunsplit(parts._replace(query=urlencode(query)))
