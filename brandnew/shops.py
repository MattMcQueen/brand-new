"""Links to other UK bookshops and record shops, for people who'd rather not use Amazon.

Plain links built from the ISBN or a search, never fetched. None of them
earn anything; if an affiliate scheme is joined later, its code goes into the link here.
"""
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Shop:
    name: str
    search: str     # "{q}" is replaced with the url-encoded search words
    by_isbn: str = ""  # books: "{isbn}" is replaced; each of these lands on the book's own page


BOOKSHOPS = (
    Shop("Waterstones", "https://www.waterstones.com/books/search/term/{q}",
         by_isbn="https://www.waterstones.com/books/search/term/{isbn}"),
    Shop("Bookshop.org", "https://uk.bookshop.org/search?keywords={q}",
         by_isbn="https://uk.bookshop.org/book/{isbn}"),
    Shop("Foyles", "https://www.foyles.co.uk/search?term={q}",
         by_isbn="https://www.foyles.co.uk/search?term={isbn}"),
    Shop("Blackwell's", "https://blackwells.co.uk/bookshop/search/?keyword={q}",
         by_isbn="https://blackwells.co.uk/bookshop/product/{isbn}"),
    Shop("Hive", "https://www.hive.co.uk/Search/Keyword?keyword={q}",
         by_isbn="https://www.hive.co.uk/Search/Keyword?keyword={isbn}"),
)


# No ISBN for albums, so these are all artist + title searches.
RECORD_SHOPS = (
    Shop("HMV", "https://hmv.com/search?searchtext={q}"),
    Shop("Rough Trade", "https://www.roughtrade.com/en-gb/search?q={q}"),
    Shop("Norman Records", "https://www.normanrecords.com/cloudsearch/index.php?q={q}"),
    Shop("Banquet Records", "https://www.banquetrecords.com/search?q={q}"),
    Shop("Resident", "https://www.resident-music.com/search?q={q}"),
)


def book_links(isbn: str | None, title: str, by: str, uk_edition: bool) -> list[tuple[str, str]]:
    """(shop name, url) pairs. Like the Amazon links: straight to the book for a UK edition,
    otherwise a title + author search, because shops only know the edition they sell."""
    if uk_edition and isbn:
        return [(s.name, s.by_isbn.format(isbn=isbn)) for s in BOOKSHOPS]
    q = quote_plus(f"{title.split(':')[0].strip()} {by.split(',')[0].strip()}")
    return [(s.name, s.search.format(q=q)) for s in BOOKSHOPS]


def album_links(artist: str, title: str) -> list[tuple[str, str]]:
    q = quote_plus(f"{artist} {title}")
    return [(s.name, s.search.format(q=q)) for s in RECORD_SHOPS]


def links_for(kind: str, id_: str, title: str, by: str, uk_edition: bool) -> list[tuple[str, str]]:
    return book_links(id_, title, by, uk_edition) if kind == "books" else album_links(by, title)
