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
    q = gb.queries(("horror",), TODAY)
    assert q[:2] == ['subject:"fiction / horror" 2026', 'subject:"fiction / horror" 2026 novel']
    assert len(q) == len(gb.VARIATIONS) and not any("2027" in x for x in q)
    assert 'subject:"fiction / horror" 2027' in gb.queries(("horror",), date(2026, 11, 1))


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
