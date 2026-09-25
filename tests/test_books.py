from datetime import date, timedelta

import pytest

from brandnew.sources import google_books as gb

TODAY = date(2026, 9, 25)


def item(title="A Novel", days=0, isbn="9780306406157", cats=("Fiction",), publisher="HarperCollins UK", date_str=None,
         lang="en", thumb="http://books.google.com/x?id=1&edge=curl", authors=("Ann Author",)):
    ids = [{"type": "ISBN_13", "identifier": isbn}] if isbn else []
    v = {"title": title, "authors": list(authors), "publisher": publisher, "language": lang,
         "publishedDate": date_str or (TODAY + timedelta(days=days)).isoformat(),
         "industryIdentifiers": ids, "infoLink": "https://books.google.co.uk/books?id=1"}
    if cats is not None:
        v["categories"] = list(cats)
    if thumb:
        v["imageLinks"] = {"thumbnail": thumb}
    return {"volumeInfo": v}


def test_to_release():
    r = gb.to_release(item(days=3), "horror", TODAY)
    assert r.id == "9780306406157" and r.genres == ["horror"]
    assert r.amazon_url == "https://www.amazon.co.uk/dp/0306406152"
    assert r.cover == "https://books.google.com/x?id=1"
    assert r.info_url.startswith("https://books.google.co.uk/")


@pytest.mark.parametrize("kw", [
    dict(date_str="2026-10"),                  # month only
    dict(days=-15), dict(days=91),             # outside the window
    dict(isbn=None),
    dict(lang="fr"),
    dict(cats=("Literary Criticism",)),        # non-fiction
    dict(publisher="Routledge"),
    dict(title="Study Guide to Some Novel"),
    dict(title="Harlequin Intrigue November 2026 - Box Set 1 of 2"),
    dict(title="Medical Romance December 2026 Books 1-4: Midwife's Baby"),
    dict(authors=()),
])
def test_rejects(kw):
    assert gb.to_release(item(**kw), "horror", TODAY) is None


@pytest.mark.parametrize("title, subtitle, expected", [
    ("Dark Waters: Now a major ITV Drama 'THE DARK'", None, "Dark Waters"),
    ("Die Famous: A Novel", None, "Die Famous"),
    ("Die Famous", "A Novel", "Die Famous"),
    ("Suffer In Silence: the brand new gripping Katie Maguire", None, "Suffer In Silence"),
    ("K-9 In Pursuit (K-9 Avalanche Rescue, Book 4) (Mills & Boon Heroes)", None,
     "K-9 In Pursuit (K-9 Avalanche Rescue, Book 4)"),
    ("King Zero: The New James Bond Novel", None, "King Zero: The New James Bond Novel"),
    ("Zone", "Book Three of the Meiji Trilogy", "Zone: Book Three of the Meiji Trilogy"),
])
def test_clean_title(title, subtitle, expected):
    assert gb.clean_title(title, subtitle) == expected


def test_amazon_link_direct_only_for_uk_publishers():
    uk = gb.to_release(item("Night: A Ghost Story", publisher="Hachette UK"), "horror", TODAY)
    us = gb.to_release(item("Night: A Ghost Story", publisher="Ballantine Books", authors=("Ann Author", "Bo B")),
                       "horror", TODAY)
    assert uk.amazon_url == "https://www.amazon.co.uk/dp/0306406152"
    assert us.amazon_url == "https://www.amazon.co.uk/s?k=Night+Ann+Author&i=stripbooks"


def test_no_categories_is_allowed():
    assert gb.to_release(item(cats=None), "horror", TODAY) is not None


def test_queries_cover_next_year_near_year_end():
    q = gb.queries(("fiction / horror",), TODAY)
    assert q[:2] == ['subject:"fiction / horror" 2026', 'subject:"fiction / horror" 2026 novel']
    assert len(q) == len(gb.VARIATIONS) and not any("2027" in x for x in q)
    assert 'subject:"fiction / horror" 2027' in gb.queries(("fiction / horror",), date(2026, 11, 1))


def test_merge_editions_and_genres():
    a = gb.to_release(item("Night: A Novel", isbn="9791234567896", days=1), "horror", TODAY)
    b = gb.to_release(item("Night", days=5, thumb=None), "literary-fiction", TODAY)
    c = gb.to_release(item("Night", isbn="9780804429573", days=2), "horror", TODAY)
    [m] = gb.merge([a, b, c])
    assert m.id == "9780804429573"  # 978 and has a cover
    assert m.genres == ["horror", "literary-fiction"]


def test_key_from_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GOOGLE_BOOKS_KEY", raising=False)
    f = tmp_path / "k.txt"
    f.write_text(" secret \n", encoding="utf-8")
    monkeypatch.setenv("GOOGLE_BOOKS_KEY_FILE", str(f))
    assert gb.api_key() == "secret"


class FakeApi:
    """Stands in for net.get_json: one fresh in-window book per call, or an error on chosen calls."""
    def __init__(self, fail_on=(), error=None):
        self.calls, self.fail_on, self.error = 0, set(fail_on), error

    def __call__(self, url):
        self.calls += 1
        if self.calls in self.fail_on:
            raise self.error
        isbn = f"978{self.calls:010d}"
        cats = ("Computers / Security / General",) if "computers" in url else ("Fiction",)
        return {"items": [item(f"Book {self.calls}", isbn=isbn, days=1, cats=cats)]}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_KEY", "k")


def test_fetch_stays_within_budget(key):
    api = FakeApi()
    books = gb.fetch(TODAY, get_json=api)
    assert api.calls <= gb.MAX_CALLS
    share = gb.MAX_CALLS // len(gb.config.BOOK_GENRES)
    assert api.calls == sum(min(share, len(gb.queries(g.terms, TODAY, g.variations or gb.VARIATIONS)) * gb.PAGES) for g in gb.config.BOOK_GENRES)
    assert {g for b in books for g in b.genres} == {g.slug for g in gb.config.BOOK_GENRES}


def test_quota_exhausted_keeps_what_was_found(key):
    api = FakeApi(fail_on=range(100, 10_000), error=gb.net.QuotaExhausted("daily quota used up"))
    books = gb.fetch(TODAY, get_json=api)
    assert len(books) == 99
    assert api.calls == 100  # stopped at the first quota error, no retries or later genres
    assert {g for b in books for g in b.genres} == {"crime-thrillers", "sf-fantasy"}


def test_quota_exhausted_with_nothing_found_raises(key):
    api = FakeApi(fail_on=range(1, 10_000), error=gb.net.QuotaExhausted("daily quota used up"))
    with pytest.raises(gb.net.QuotaExhausted):
        gb.fetch(TODAY, get_json=api)


def test_failed_genre_is_skipped(key):
    api = FakeApi(fail_on={1}, error=RuntimeError("boom"))
    books = gb.fetch(TODAY, get_json=api)
    genres = {g for b in books for g in b.genres}
    assert "crime-thrillers" not in genres and "literary-fiction" in genres


def test_uk_edition_flag():
    assert gb.to_release(item(publisher="Pan Macmillan"), "horror", TODAY).uk_edition
    assert not gb.to_release(item(publisher="Berkley"), "horror", TODAY).uk_edition


@pytest.mark.parametrize("isbn,publisher,uk", [
    ("9781529445282", "Hachette UK", True),
    ("9780316535984", "Hachette UK", False),    # Little, Brown and Company (US): Die Famous
    ("9789357317511", "Hachette UK", False),    # Hachette India
    ("9798260200384", "Raven Books", False),    # 979-8 is a US range
    ("9781529445282", "Berkley", False),
    (None, "Hachette UK", False),
])
def test_uk_edition_needs_a_uk_publisher_and_isbn(isbn, publisher, uk):
    assert gb.is_uk_edition(publisher, isbn) is uk


def test_relink_fixes_data_saved_before_the_rules():
    from brandnew import shops
    from brandnew.models import Release
    old = {"kind": "books", "id": "9781529445282", "title": "The Thoroughbreds", "by": "Elin Hilderbrand",
           "date": "2026-10-01", "source": "google-books", "publisher": "Hachette UK",
           "amazon_url": "https://www.amazon.co.uk/s?k=9781529445282&i=stripbooks"}  # no uk_edition field
    us = old | {"id": "9780316535984", "title": "Die Famous", "amazon_url": "https://www.amazon.co.uk/dp/0316535982"}
    uk_book, us_book = gb.relink([Release.from_dict(old), Release.from_dict(us)])
    assert uk_book.uk_edition and uk_book.amazon_url == "https://www.amazon.co.uk/dp/1529445280"
    links = dict(shops.book_links(uk_book.id, uk_book.title, uk_book.by, uk_book.uk_edition))
    assert links["Bookshop.org"] == "https://uk.bookshop.org/book/9781529445282"
    assert not us_book.uk_edition and us_book.amazon_url == "https://www.amazon.co.uk/s?k=Die+Famous+Elin+Hilderbrand&i=stripbooks"


def test_tech_genre_keeps_computing_books_only():
    computing = item("Building Secure AI Systems", cats=("Computers / Security / General",), publisher="O'Reilly Media")
    assert gb.to_release(computing, "tech-ai", TODAY, "computers") is not None
    assert gb.to_release(item("A Novel"), "tech-ai", TODAY, "computers") is None           # fiction
    assert gb.to_release(computing, "horror", TODAY) is None                                # not fiction
    exam = item("CompTIA Security+ Exam Guide", cats=("Computers / Security / General",), publisher="McGraw Hill")
    assert gb.to_release(exam, "tech-ai", TODAY, "computers") is None
    wiley = item("AI Engineering", cats=("Computers / Artificial Intelligence",), publisher="Wiley")
    assert gb.to_release(wiley, "tech-ai", TODAY, "computers") is not None


def test_tech_queries_use_computing_subjects_and_own_variations():
    g = next(g for g in gb.config.BOOK_GENRES if g.slug == "tech-ai")
    q = gb.queries(g.terms, TODAY, g.variations)
    assert q[0] == 'subject:"computers / artificial intelligence" 2026'
    assert not any("novel" in x or "book 1" in x for x in q)
