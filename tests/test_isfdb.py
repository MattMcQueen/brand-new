import json

import pytest
from datetime import date

from brandnew.sources import isfdb

TODAY = date(2026, 9, 26)


def row(day, author, title, pub_id, isbn, tags="&nbsp;", kind="Novel", reprint="&nbsp;", publisher="Tor"):
    """One row, marked up the way the ISFDB's Monthly Bibliography does it."""
    return f'''<tr align=left class="table1">
<td>
{day}
</td>
<td>
<a href="https://www.isfdb.org/cgi-bin/ea.cgi?1" dir="ltr">{author}</a>
</td>
<td>
<a href="https://www.isfdb.org/cgi-bin/pl.cgi?{pub_id}" dir="ltr">{title}</a> &#8226; <a class = "italic" href="https://www.isfdb.org/cgi-bin/pe.cgi?2" dir="ltr">Some Series</a> #2
</td>
<td>
{reprint}
</td>
<td>
{tags}
</td>
<td>
{kind}
</td>
<td>
<a href="https://www.isfdb.org/cgi-bin/publisher.cgi?23" dir="ltr">{publisher}</a>
</td>
<td dir="ltr">{isbn}</td>
<td>
<div class="tooltip tooltipleft">$28.99<sup class="mouseover">?</sup><span class="tooltiptext">US dollar</span></div>
</td>
<td>
384
</td>
<td>
hc
</td>
</tr>'''


PAGE = f'''<h2 id = "adult" class="centered">Adult</h2><table>
{row("2026-09-29", "Seanan McGuire", "A Divided Duty", 1123465, "978-1-250-37527-8")}
{row("2026-10-06", "Ann Author", "Star Road", 11, "978-1-250-00000-2", tags="science fiction , hard sf")}
{row("2026-10-06", "Old Hand", "Classic Reissue", 12, "978-1-250-00001-9", reprint="1972")}
{row("2026-10-06", "Hans Autor", "Novembersommer", 13, "978-3-7577-0240-3")}
{row("2026-10-06", "Chap Book", "Tiny Tale", 14, "978-1-250-00002-6", kind="Chapbook")}
{row("2026-10-00", "No Day", "Sometime", 15, "978-1-250-00003-3")}
{row("2026-10-06", "Ann Author", "Star Road", 17, "978-1-250-00004-0", tags="science fiction")}
</table><h2 id = "ya" class="centered">Young Adult and Juvenile</h2><table>
{row("2026-10-13", "Kid Writer", "Dragon School", 16, "978-1-665-00000-1", tags="juvenile fantasy")}
</table>'''


def test_parse_month():
    rows = isfdb.parse_month(PAGE)
    first = rows[0]
    assert first == {"date": "2026-09-29", "authors": ["Seanan McGuire"], "title": "A Divided Duty",
                     "url": "https://www.isfdb.org/cgi-bin/pl.cgi?1123465", "reprint": False, "tags": [],
                     "type": "Novel", "publisher": "Tor", "isbn": "9781250375278", "format": "hc",
                     "section": "adult"}
    assert rows[1]["tags"] == ["science fiction", "hard sf"]
    assert rows[2]["reprint"] and rows[4]["type"] == "Chapbook"
    assert rows[-1]["section"] == "ya"


def test_isbn13():
    assert isfdb.isbn13("978-1-250-37527-8") == "9781250375278"
    assert isfdb.isbn13("0-306-40615-2") == "9780306406157"  # ISBN-10 converted
    assert isfdb.isbn13("TOR 12345") is None


def test_months_in_window_puts_this_month_first():
    assert isfdb.months_in_window(TODAY) == ["2026-09", "2026-10", "2026-11", "2026-12"]


def test_genres_from_google_subjects_or_isfdb_tags():
    assert isfdb.genres_for(["Fiction / Science Fiction / Space Opera"], [], "adult") == ["science-fiction"]
    assert isfdb.genres_for(["Fiction / Fantasy / Urban", "Fiction / Romance / Paranormal"], [], "adult") == \
        ["romance", "fantasy"]
    assert isfdb.genres_for(["Juvenile Fiction / Fantasy & Magic"], [], "ya") == ["childrens"]
    assert isfdb.genres_for(["Young Adult Fiction / Fantasy / Epic"], [], "ya") == []  # no YA genre
    assert isfdb.genres_for([], ["science fiction", "hard sf"], "adult") == ["science-fiction"]
    assert isfdb.genres_for([], ["juvenile fantasy"], "adult") == []
    assert isfdb.genres_for([], ["fantasy"], "ya") == []  # tags only count in the adult sections


class FakeGoogle:
    """isbn:<n> searches and full records. Books not in `subjects` are unknown to Google."""
    def __init__(self, subjects):
        self.subjects, self.calls = subjects, 0

    def __call__(self, url):
        self.calls += 1
        if "q=isbn" in url:
            isbn = url.split("isbn%3A")[1].split("&")[0]
            return {"items": [{"id": isbn}]} if isbn in self.subjects else {}
        vid = url.split("/volumes/")[1].split("?")[0]
        return {"volumeInfo": {"categories": self.subjects[vid], "language": "en",
                               "imageLinks": {"thumbnail": "http://books.google.com/x?id=1&edge=curl"}}}


def test_fetch_files_books_by_subject_and_caches(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_KEY", "k")
    google = FakeGoogle({"9781250375278": ["Fiction / Fantasy / Urban"],
                         "9781250000002": ["Fiction / Science Fiction / Hard Science Fiction"]})
    pages = []
    cache = tmp_path / "isfdb.json"
    books = isfdb.fetch(TODAY, cache, get_json=google, get_text=lambda url: pages.append(url) or PAGE)
    assert pages == ["https://www.isfdb.org/cgi-bin/fc.cgi?date+9+2026"]  # one page per run, this month first
    by_title = {b.title: b for b in books}
    assert set(by_title) == {"A Divided Duty", "Star Road"}  # no reprint, German, chapbook, undated or YA-only book
    assert by_title["A Divided Duty"].genres == ["fantasy"]
    star = by_title["Star Road"]
    assert star.genres == ["science-fiction"] and star.source == "isfdb" and star.date == date(2026, 10, 6)
    assert star.info_url == "https://www.isfdb.org/cgi-bin/pl.cgi?11" and star.cover == "https://books.google.com/x?id=1&fife=w320"
    assert star.amazon_url == "https://www.amazon.co.uk/s?k=Star+Road+Ann+Author&i=stripbooks"
    looked_up = google.calls  # 2 known books x 2 calls, plus 1 search for the unknown one
    assert looked_up == 5

    # Next run: the next month page, and no lookups for books already known
    books = isfdb.fetch(TODAY, cache, get_json=google, get_text=lambda url: pages.append(url) or PAGE)
    assert pages[-1] == "https://www.isfdb.org/cgi-bin/fc.cgi?date+10+2026"
    assert google.calls == looked_up and len(books) == 2  # the same books in both cached months count once
    assert set(json.loads(cache.read_text(encoding="utf-8"))["months"]) == {"2026-09", "2026-10"}


def test_fetch_keeps_cached_months_when_the_page_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_BOOKS_KEY", "k")
    google = FakeGoogle({"9781250000002": ["Fiction / Science Fiction"]})
    cache = tmp_path / "isfdb.json"
    isfdb.fetch(TODAY, cache, get_json=google, get_text=lambda url: PAGE)

    def broken(url):
        raise RuntimeError("503")
    books = isfdb.fetch(TODAY, cache, get_json=google, get_text=broken)
    assert [b.title for b in books] == ["Star Road"]


def test_isfdb_only_fetch_keeps_previous_data(tmp_path, monkeypatch):
    from brandnew import __main__ as cli, store
    from brandnew.models import Release
    from brandnew.ukdates import now_uk
    today = now_uk().date()
    old_book = Release(kind="books", id="9780000000001", title="Old Book", by="A", date=today, source="google-books",
                       amazon_url="", genres=["horror"])
    album = Release(kind="music", id="m", title="Album", by="B", date=today, source="listenbrainz",
                    amazon_url="", genres=["rock"])
    previous = tmp_path / "prev.json"
    store.save(previous, [old_book, album], now_uk())
    new_book = Release(kind="books", id="9781250000002", title="Star Road", by="Ann Author", date=today,
                       source="isfdb", amazon_url="", genres=["science-fiction"])
    monkeypatch.setattr(cli.isfdb, "fetch", lambda day, cache: [new_book])
    monkeypatch.setattr(cli.google_books, "fetch", lambda day: pytest.fail("no main Google Books fetch"))
    monkeypatch.setattr(cli.listenbrainz, "fetch", lambda day, cache: pytest.fail("no ListenBrainz fetch"))
    out = tmp_path / "data.json"
    assert cli.main(["fetch", "--previous", str(previous), "--data", str(out), "--isfdb-only"]) == 0
    _, releases = store.load(out)
    assert {r.title for r in releases} == {"Old Book", "Star Road", "Album"}

