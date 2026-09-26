from datetime import date, timedelta

import pytest

from brandnew.sources import google_books as gb

TODAY = date(2026, 9, 25)


def item(title="A Novel", days=0, isbn="9780306406157", cats=("Fiction",), publisher="HarperCollins UK", date_str=None,
         lang="en", thumb="http://books.google.com/x?id=1&edge=curl", authors=("Ann Author",), subtitle=None):
    ids = [{"type": "ISBN_13", "identifier": isbn}] if isbn else []
    v = {"title": title, "authors": list(authors), "publisher": publisher, "language": lang,
         "publishedDate": date_str or (TODAY + timedelta(days=days)).isoformat(),
         "industryIdentifiers": ids, "infoLink": "https://books.google.co.uk/books?id=1"}
    if subtitle:
        v["subtitle"] = subtitle
    if cats is not None:
        v["categories"] = list(cats)
    if thumb:
        v["imageLinks"] = {"thumbnail": thumb}
    return {"volumeInfo": v}


def test_to_release():
    r = gb.to_release(item(days=3), "horror", TODAY)
    assert r.id == "9780306406157" and r.genres == ["horror"]
    assert r.amazon_url == "https://www.amazon.co.uk/s?k=A+Novel+Ann+Author&i=stripbooks"
    assert r.cover == "https://books.google.com/x?id=1&fife=w300"
    assert r.cover_2x == "https://books.google.com/x?id=1&fife=w600"
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
    dict(title="The Poppy Denby Investigates Boxset", subtitle="Books 1-3 in the beloved series"),
    dict(title="The Fenwick Mysteries Box-Set"),
    dict(title="Murder at the Manor", subtitle="Books 4 - 6"),
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


def test_amazon_link_is_a_search_whoever_the_publisher():
    for publisher in ("Hachette UK", "Ballantine Books", "Embla Books"):
        r = gb.to_release(item("Night: A Ghost Story", publisher=publisher, authors=("Ann Author", "Bo B")), "horror", TODAY)
        assert r.amazon_url == "https://www.amazon.co.uk/s?k=Night+Ann+Author&i=stripbooks"


def test_subtitles_can_be_ordinary():
    assert gb.to_release(item("Zone", subtitle="Book Three of the Meiji Trilogy"), "horror", TODAY) is not None


def test_no_categories_is_allowed():
    assert gb.to_release(item(cats=None), "horror", TODAY) is not None


def test_queries_cover_next_year_near_year_end():
    q = gb.queries(("fiction / horror",), TODAY)
    assert q[:2] == ['subject:"fiction / horror" 2026', 'subject:"fiction / horror" 2026 novel']
    assert len(q) == len(gb.VARIATIONS) and not any("2027" in x for x in q)
    assert 'subject:"fiction / horror" 2027' in gb.queries(("fiction / horror",), date(2026, 11, 1))


def test_childrens_books_use_their_own_subject():
    childrens = next(g for g in gb.config.BOOK_GENRES if g.slug == "childrens")
    assert gb.queries(childrens.terms, TODAY)[0] == 'subject:"juvenile fiction" 2026'
    assert gb.to_release(item(cats=("Juvenile Fiction",)), "childrens", TODAY) is not None
    assert gb.to_release(item(cats=("Juvenile Nonfiction",)), "childrens", TODAY) is None


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
        return {"items": [item(f"Book {self.calls}", isbn=isbn, days=1)]}


@pytest.fixture
def key(monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_KEY", "k")


def test_fetch_stays_within_budget(key):
    api = FakeApi()
    books = gb.fetch(TODAY, get_json=api)
    assert api.calls <= gb.MAX_CALLS
    share = gb.MAX_CALLS // len(gb.config.BOOK_GENRES)
    assert api.calls == sum(min(share, len(gb.queries(g.terms, TODAY)) * gb.PAGES) for g in gb.config.BOOK_GENRES)
    assert {g for b in books for g in b.genres} == {g.slug for g in gb.config.BOOK_GENRES}


def test_quota_exhausted_keeps_what_was_found(key):
    api = FakeApi(fail_on=range(100, 10_000), error=gb.net.QuotaExhausted("daily quota used up"))
    books = gb.fetch(TODAY, get_json=api)
    assert len(books) == 99
    assert api.calls == 100  # stopped at the first quota error, no retries or later genres
    assert {g for b in books for g in b.genres} == {"crime-thrillers", "childrens", "romance"}  # most popular first


def test_quota_exhausted_with_nothing_found_raises(key):
    api = FakeApi(fail_on=range(1, 10_000), error=gb.net.QuotaExhausted("daily quota used up"))
    with pytest.raises(gb.net.QuotaExhausted):
        gb.fetch(TODAY, get_json=api)


def test_failed_genre_is_skipped(key):
    api = FakeApi(fail_on={1}, error=RuntimeError("boom"))
    books = gb.fetch(TODAY, get_json=api)
    genres = {g for b in books for g in b.genres}
    assert "crime-thrillers" not in genres and "literary-fiction" in genres


def test_relink_turns_older_isbn_links_into_searches():
    from brandnew.models import Release
    old = {"kind": "books", "id": "9781529445282", "title": "The Thoroughbreds", "by": "Elin Hilderbrand",
           "date": "2026-10-01", "source": "google-books", "publisher": "Hachette UK", "uk_edition": True,
           "amazon_url": "https://www.amazon.co.uk/dp/1529445280",  # saved by an older version
           "cover": "https://books.google.com/books/content?id=1&zoom=1"}  # 128 pixels wide
    album = {"kind": "music", "id": "m", "title": "A", "by": "B", "date": "2026-10-01", "source": "listenbrainz",
             "amazon_url": "https://www.amazon.co.uk/s?k=B+A&i=popular"}
    book, same_album = gb.relink([Release.from_dict(old | {"genres": ["sf-fantasy", "fantasy", "horror"]}),
                                  Release.from_dict(album)])
    assert book.genres == ["fantasy", "horror"]  # the old combined genre is filed under fantasy
    assert book.amazon_url == "https://www.amazon.co.uk/s?k=The+Thoroughbreds+Elin+Hilderbrand&i=stripbooks"
    assert book.cover == "https://books.google.com/books/content?id=1&zoom=1&fife=w300"
    assert book.cover_2x == "https://books.google.com/books/content?id=1&zoom=1&fife=w600"
    assert gb.relink([book])[0].cover == book.cover  # the same however many times it's run
    assert same_album.amazon_url == album["amazon_url"]
