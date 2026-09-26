"""Links to other UK bookshops and record shops, for people who'd rather not use Amazon.

Plain search links, never fetched. None of them
earn anything; if an affiliate scheme is joined later, its code goes into the link here.
"""
from dataclasses import dataclass
from urllib.parse import quote, quote_plus


@dataclass(frozen=True)
class Shop:
    name: str
    search: str     # "{q}" is replaced with the search words, url-encoded ("{qp}": encoded for a path)
    formats: str = ""  # shown next to the name, e.g. "ebooks & audiobooks"


@dataclass(frozen=True)
class Group:
    heading: str
    links: list[tuple[str, str, str]]  # (shop name, url, formats)
    note: str = ""


# Title + author searches, like the Amazon links: the ISBN we have is often the ebook's, which
# a bookshop's product page wouldn't know.
BOOKSHOPS = (
    Shop("Waterstones", "https://www.waterstones.com/books/search/term/{q}"),
    Shop("Bookshop.org", "https://uk.bookshop.org/search?keywords={q}"),
    Shop("Foyles", "https://www.foyles.co.uk/search?term={q}"),
    Shop("Blackwell's", "https://blackwells.co.uk/bookshop/search/?keyword={q}"),
    Shop("Hive", "https://www.hive.co.uk/Search/Keyword?keyword={q}"),
)

# Ebooks and audiobooks have their own ISBNs, and not every book has them, so these are
# always title + author searches. No Audible: it's Amazon's, and only the Audible link under the
# Amazon button (through amazon.co.uk, with the Associates tag) can earn anything.
DIGITAL_SHOPS = (
    Shop("Kobo", "https://www.kobo.com/gb/en/search?query={q}", formats="ebooks & audiobooks"),
    Shop("Google Play Books", "https://play.google.com/store/search?q={q}&c=books&gl=GB",
         formats="ebooks & audiobooks"),
    Shop("Spotify", "https://open.spotify.com/search/{qp}/audiobooks", formats="audiobooks"),
)
DIGITAL_NOTE = "Not every book has an ebook or audiobook, so these open a search."

# No ISBN for albums, so these are all artist + title searches.
RECORD_SHOPS = (
    Shop("HMV", "https://hmv.com/search?searchtext={q}"),
    Shop("Rough Trade", "https://www.roughtrade.com/en-gb/search?q={q}"),
    Shop("Norman Records", "https://www.normanrecords.com/cloudsearch/index.php?q={q}"),
    Shop("Banquet Records", "https://www.banquetrecords.com/search?q={q}"),
    Shop("Resident", "https://www.resident-music.com/search?q={q}"),
)


# Streaming (and Bandcamp, which streams and sells). Artist + title searches; none earn anything.
STREAMING = (
    Shop("Spotify", "https://open.spotify.com/search/{qp}/albums"),
    Shop("Apple Music", "https://music.apple.com/gb/search?term={qp}"),
    Shop("YouTube Music", "https://music.youtube.com/search?q={q}"),
    Shop("Amazon Music", "https://music.amazon.co.uk/search/{qp}"),
    Shop("Deezer", "https://www.deezer.com/en/search/{qp}/album"),
    Shop("Bandcamp", "https://bandcamp.com/search?q={q}&item_type=a"),
)
# Before release day a streaming search may only find singles, or a pre-save.
UPCOMING_NOTE = "Out on {date}. Until then you may only find singles, or a pre-save."


def _book_query(title: str, by: str) -> str:
    return f"{title.split(':')[0].strip()} {by.split(',')[0].strip()}"


def _searches(shops: tuple[Shop, ...], words: str) -> list[tuple[str, str]]:
    return [(s.name, s.search.format(q=quote_plus(words), qp=quote(words))) for s in shops]


def book_links(title: str, by: str) -> list[tuple[str, str]]:
    """(shop name, url) pairs."""
    return _searches(BOOKSHOPS, _book_query(title, by))


def digital_links(title: str, by: str) -> list[tuple[str, str]]:
    return _searches(DIGITAL_SHOPS, _book_query(title, by))


def album_links(artist: str, title: str) -> list[tuple[str, str]]:
    return _searches(RECORD_SHOPS, f"{artist} {title}")


def listen_links(artist: str, title: str) -> list[tuple[str, str]]:
    return _searches(STREAMING, f"{artist} {title}")


def _group(heading: str, shops: tuple[Shop, ...], links: list[tuple[str, str]], note: str = "") -> Group:
    return Group(heading, [(name, url, s.formats) for s, (name, url) in zip(shops, links)], note)


def groups_for(kind: str, title: str, by: str, out_on: str = "") -> list[Group]:
    """What the "Other shops" popover lists for a release. `out_on` is the date (as the site shows
    it) of an album that isn't out yet: its record shops come first, as they can take pre-orders."""
    if kind == "books":
        return [_group("Bookshops", BOOKSHOPS, book_links(title, by)),
                _group("Ebooks & audiobooks", DIGITAL_SHOPS, digital_links(title, by), DIGITAL_NOTE)]
    listen = _group("Listen", STREAMING, listen_links(by, title), UPCOMING_NOTE.format(date=out_on) if out_on else "")
    buy = _group("Record shops", RECORD_SHOPS, album_links(by, title))
    return [buy, listen] if out_on else [listen, buy]
