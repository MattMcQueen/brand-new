from datetime import date, datetime, timedelta

import pytest

from brandnew import picks, render
from brandnew.models import Release
from brandnew.ukdates import UK

TODAY = date(2026, 9, 25)
UNTIL = TODAY + timedelta(days=5)


def rel(id_, kind="books", genre="horror"):
    return Release(kind=kind, id=id_, title="Known", by="A", date=TODAY, source="google-books",
                   amazon_url="https://www.amazon.co.uk/dp/0306406152", genres=[genre])


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def fail(*a, **k):
        raise RuntimeError("no network in tests")
    monkeypatch.setattr(picks.net, "get_json", fail)


def test_load(tmp_path):
    f = tmp_path / "picks.yaml"
    f.write_text('picks:\n  - isbn: "978-0-306-40615-7"\n    until: 2026-10-01\n', encoding="utf-8")
    assert picks.load(f) == [{"isbn": "978-0-306-40615-7", "until": date(2026, 10, 1)}]
    assert picks.load(tmp_path / "missing.yaml") == []


def test_pick_from_todays_data_gets_note_and_is_a_copy():
    known = rel("9780306406157")
    [p] = picks.resolve([{"isbn": "978-0-306-40615-7", "note": " Loved it ", "until": UNTIL}], [known], TODAY)
    assert p.title == "Known" and p.note == "Loved it"
    assert known.note == ""


def test_dates_decide_what_shows():
    entries = [{"isbn": "1", "until": TODAY - timedelta(days=1)},          # finished
               {"isbn": "2", "until": UNTIL, "from": TODAY + timedelta(days=1)},  # not started
               {"isbn": "3", "until": TODAY},                                # last day
               {"isbn": "4"}]                                                # no until: skipped
    data = [rel(str(i)) for i in range(1, 5)]
    assert [p.id for p in picks.resolve(entries, data, TODAY)] == ["3"]


def test_lookup_failure_falls_back_to_yaml_details_or_skips():
    ok = {"mbid": "ABC", "title": "Album", "by": "Band", "date": "2026-10-09", "until": UNTIL, "genre": "folk"}
    [p] = picks.resolve([ok, {"mbid": "def", "until": UNTIL}], [], TODAY)
    assert (p.kind, p.id, p.title, p.date, p.genres) == ("music", "abc", "Album", date(2026, 10, 9), ["folk"])
    assert p.amazon_url == "https://www.amazon.co.uk/s?k=Band+Album&i=popular"


def test_album_lookup(monkeypatch):
    monkeypatch.setattr(picks.net, "get_json", lambda url: {
        "title": "Songs", "first-release-date": "2026-10-02",
        "artist-credit": [{"name": "A", "joinphrase": " & "}, {"name": "B", "joinphrase": ""}]})
    [p] = picks.resolve([{"mbid": "x1", "until": UNTIL, "note": "Great"}], [], TODAY)
    assert (p.by, p.title, p.date) == ("A & B", "Songs", date(2026, 10, 2))
    assert p.cover == "https://coverartarchive.org/release-group/x1/front-250"


def test_overrides_and_bad_genre_and_bad_entries():
    data = [rel("9780306406157")]
    entries = [{"isbn": "9780306406157", "title": "Better Title", "genre": "polka", "until": UNTIL},
               {"note": "no id", "until": UNTIL}]
    [p] = picks.resolve(entries, data, TODAY)
    assert p.title == "Better Title" and p.genres == ["horror"]


def test_home_page_shows_picks_and_genre_page_shows_badge(tmp_path):
    data = [rel("9780306406157")]
    chosen = picks.resolve([{"isbn": "9780306406157", "note": "Scary!", "until": UNTIL}], data, TODAY)
    render.build(data, datetime(2026, 9, 25, 5, 0, tzinfo=UK), tmp_path, TODAY, picks=chosen)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Picks of the week" in home and "Scary!" in home and "powered by Google" in home
    genre = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert "Pick of the week" in genre and "Scary!" not in genre


def test_no_picks_no_section(tmp_path):
    render.build([rel("1")], datetime(2026, 9, 25, 5, 0, tzinfo=UK), tmp_path, TODAY)
    assert "Picks of the week" not in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_committed_picks_file_is_valid():
    assert isinstance(picks.load(picks.Path("picks.yaml")), list)
