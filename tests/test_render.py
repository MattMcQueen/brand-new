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
    cards = re.findall(r'<li class="card">(.*?)\n</li>', html, re.S)  # the card's own </li> is on its own line
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
    assert main(["build", "--data", str(data), "--out", str(out), "--min-releases", "1000"]) == 3
    assert not out.exists()
    assert main(["build", "--data", str(data), "--out", str(out), "--min-releases", "10"]) == 0


def test_books_and_albums_have_other_shops(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    books = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    ids = re.findall(r'<div class="shops" id="([^"]+)" popover>', books)
    assert ids and len(ids) == len(set(ids)) == books.count('class="more-shops"')
    assert all(f'popovertarget="{i}"' in books for i in ids)
    shop_links = re.findall(r'<li><a href="([^"]+)" rel="([^"]+)"', books)
    assert shop_links and all(rel == config.OTHER_SHOP_REL and "tag=" not in href for href, rel in shop_links)
    assert "Ebooks &amp; audiobooks" in books and "open.spotify.com/search/" in books
    formats = re.findall(r'<a href="(https://www\.amazon\.co\.uk/s\?[^"]+)" rel="([^"]+)"', books)
    assert any("i=digital-text" in h for h, _ in formats) and any("i=audible" in h for h, _ in formats)
    assert all("tag=" not in h or rel == config.AFFILIATE_REL for h, rel in formats)
    music = (tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    assert music.count('class="more-shops"') == music.count('class="card"') > 0
    assert "Record shops" in music and "hmv.com/search?searchtext=" in music
    assert "Also on Amazon" not in music and "Ebooks &amp; audiobooks" not in music
    about = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert 'id="other-shops"' in about and "Waterstones, Bookshop.org, Foyles, Blackwell&#39;s and Hive" in about
    assert "HMV, Rough Trade, Norman Records, Banquet Records and Resident" in about
    assert "Kobo, Google Play Books and Spotify" in about


def test_rebuild_empties_the_output_folder_but_keeps_it(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    (out / "stale.html").write_text("old", encoding="utf-8")
    (out / "old-dir").mkdir()
    before = out.stat().st_ino
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), out, TODAY)
    assert not (out / "stale.html").exists() and not (out / "old-dir").exists()
    assert (out / "index.html").exists() and out.stat().st_ino == before


def test_static_files_are_fingerprinted(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert re.search(r'href="/static/style\.css\?v=[0-9a-f]{8}"', home)
    assert re.search(r'src="/static/app\.js\?v=[0-9a-f]{8}"', home)
    assert render.asset_url("style.css") != render.asset_url("app.js")


def test_about_page_explains_what_the_site_cant_do(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    about = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert 'id="limitations"' in about
    assert "price comparison" in about and "in stock" in about and "open a search" in about


def test_header_logo_is_the_favicon(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '<svg class="logo-mark"' in home and 'aria-hidden="true"' in home
    assert re.search(r'<link rel="icon" href="/static/favicon\.svg\?v=[0-9a-f]{8}"', home)
    assert render.logo_svg().count("<polygon") == 1  # the sticker outline


def test_kofi_button_and_line_load_nothing_from_kofi_until_clicked(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    for page in ("index.html", "books/horror/index.html", "about/index.html"):
        html = (tmp_path / page).read_text(encoding="utf-8")
        assert 'class="support-btn"' in html and 'id="kofi-panel" popover' in html
        assert "<iframe" not in html and "ko-fi.com/cdn" not in html and "storage.ko-fi.com" not in html
    assert 'class="kofi-line"' in (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert 'class="kofi-line"' in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'class="kofi-line"' not in (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert 'class="kofi-line"' not in (tmp_path / "404.html").read_text(encoding="utf-8")
    # The floating button replaced the footer's Ko-fi link.
    footer = (tmp_path / "index.html").read_text(encoding="utf-8").split('<footer class="site-footer">')[1]
    assert "Buy me a coffee" not in footer.split("</footer>")[0]
