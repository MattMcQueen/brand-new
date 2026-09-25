import re
from datetime import date, datetime, timedelta

from brandnew import config, render, sample
from brandnew.config import BOOK_GENRES
from brandnew.models import Release
from brandnew.ukdates import UK, format_date, format_updated

TODAY = date(2026, 9, 25)


def book(days: int, genre="horror", title="T") -> Release:
    return Release(kind="books", id=title, title=title, by="A", date=TODAY + timedelta(days=days),
                   source="test", amazon_url="https://www.amazon.co.uk/dp/0306406152", genres=[genre])


def test_windows():
    horror = BOOK_GENRES[3]
    page = render.genre_page(horror, [book(-8), book(-3), book(0), book(1), book(90), book(91),
                                      book(-3, genre="romance")], TODAY)
    assert page.past_days == 7
    assert [r.date for r in page.past] == [TODAY, TODAY - timedelta(days=3)]
    assert [len(rs) for _, rs in page.upcoming] == [1, 1]  # 26 Sep, 24 Dec
    assert page.upcoming[0][0] == "September 2026"  # the 26th is still September


def test_falls_back_to_two_weeks_when_last_week_is_empty():
    page = render.genre_page(BOOK_GENRES[3], [book(-10), book(-15)], TODAY)
    assert page.past_days == 14
    assert len(page.past) == 1


def test_uk_formats():
    assert format_date(date(2026, 10, 2)) == "Fri 2 Oct 2026"
    assert format_updated(datetime(2026, 9, 25, 5, 31, tzinfo=UK)) == "Friday 25 September 2026 at 05:31 BST"
    assert format_updated(datetime(2026, 12, 1, 5, 0, tzinfo=UK)) == "Tuesday 1 December 2026 at 05:00 GMT"


def test_build_site(tmp_path):
    releases = sample.releases(TODAY)
    generated = datetime(2026, 9, 25, 5, 31, tzinfo=UK)
    pages = render.build(releases, generated, tmp_path, TODAY, amazon_tag="test-21")
    assert "/" in pages and "/books/horror/" in pages and "/music/hip-hop/" in pages
    html = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    links = re.findall(r'<a class="buy" href="([^"]+)" rel="([^"]+)"', html)
    assert links and all("tag=test-21" in href and rel == config.AFFILIATE_REL for href, rel in links)
    for page in ("index.html", "about/index.html", "books/horror/index.html"):
        text = (tmp_path / page).read_text(encoding="utf-8")
        assert config.AMAZON_DISCLOSURE in text
        assert "ListenBrainz" in text and "Google Books" in text and "Cover Art Archive" in text
        assert "05:31 BST" in text
    assert (tmp_path / "data" / "releases.json").exists()


def test_cards_have_the_same_parts_so_rows_line_up(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    html = (tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    cards = re.findall(r'<li class="card">(.*?)</li>', html, re.S)
    parts = [re.findall(r'^  <\w+ class="([\w-]+)', c, re.M) for c in cards]
    assert cards and all(p == ["cover", "card-title", "card-by", "card-date", "card-extra", "card-buy", "card-source"]
                         for p in parts)


def test_about_page_explains_affiliate_links(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    about = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert 'id="affiliate-links"' in about and "affiliate link" in about
    assert "You don't pay a penny more" in about and f"tag={config.AMAZON_TAG}" in about
    assert 'href="/about/#affiliate-links"' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_default_tag_is_used(tmp_path, monkeypatch):
    from brandnew.__main__ import main
    monkeypatch.delenv("AMAZON_TAG", raising=False)
    assert main(["build", "--sample", "--out", str(tmp_path)]) == 0
    html = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert "tag=matsbasblo-21" in html


def test_build_refuses_thin_data(tmp_path):
    from brandnew import store
    from brandnew.__main__ import main
    data = tmp_path / "r.json"
    store.save(data, sample.releases(TODAY), datetime(2026, 9, 25, 5, 0, tzinfo=UK))
    out = tmp_path / "dist"
    assert main(["build", "--data", str(data), "--out", str(out), "--min-releases", "1000"]) == 1
    assert not out.exists()
    assert main(["build", "--data", str(data), "--out", str(out), "--min-releases", "10"]) == 0
