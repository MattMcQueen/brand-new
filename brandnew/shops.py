"""Links to other UK bookshops, for people who'd rather not use Amazon.

Plain links built from the ISBN (or a title + author search), never fetched. None of them
earn anything; if an affiliate scheme is joined later, its code goes into the link here.
"""
from dataclasses import dataclass
from urllib.parse import quote_plus


@dataclass(frozen=True)
class Shop:
    name: str
    by_isbn: str    # "{isbn}" is replaced; each of these lands on the book's own page
    search: str     # "{q}" is replaced with the url-encoded title + author


BOOKSHOPS = (
    Shop("Waterstones", "https://www.waterstones.com/books/search/term/{isbn}",
         "https://www.waterstones.com/books/search/term/{q}"),
    Shop("Bookshop.org", "https://uk.bookshop.org/book/{isbn}",
         "https://uk.bookshop.org/search?keywords={q}"),
    Shop("Foyles", "https://www.foyles.co.uk/search?term={isbn}",
         "https://www.foyles.co.uk/search?term={q}"),
    Shop("Blackwell's", "https://blackwells.co.uk/bookshop/product/{isbn}",
         "https://blackwells.co.uk/bookshop/search/?keyword={q}"),
    Shop("Hive", "https://www.hive.co.uk/Search/Keyword?keyword={isbn}",
         "https://www.hive.co.uk/Search/Keyword?keyword={q}"),
)


def book_links(isbn: str | None, title: str, by: str, uk_edition: bool) -> list[tuple[str, str]]:
    """(shop name, url) pairs. Like the Amazon links: straight to the book for a UK edition,
    otherwise a title + author search, because shops only know the edition they sell."""
    if uk_edition and isbn:
        return [(s.name, s.by_isbn.format(isbn=isbn)) for s in BOOKSHOPS]
    q = quote_plus(f"{title.split(':')[0].strip()} {by.split(',')[0].strip()}")
    return [(s.name, s.search.format(q=q)) for s in BOOKSHOPS]
