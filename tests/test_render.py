import json
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
    cards = re.findall(r'<li class="card" data-id="[^"]*">(.*?)\n</li>', html, re.S)  # the card's own </li> is on its own line
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
    assert 'id="other-shops"' in about
    chips = [re.findall(r"<li>([^<]+)</li>", ul) for ul in re.findall(r'<ul class="shop-chips" role="list">(.*?)</ul>', about)]
    assert chips == [["Waterstones", "Bookshop.org", "Foyles", "Blackwell&#39;s", "Hive"],
                     ["Kobo", "Google Play Books", "Spotify"],
                     ["Spotify", "Apple Music", "YouTube Music", "Amazon Music", "Deezer", "Bandcamp"],
                     ["HMV", "Rough Trade", "Norman Records", "Banquet Records", "Resident"]]


def test_about_page_sections_can_be_jumped_to(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    about = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    nav = re.search(r'<nav class="on-page" aria-label="On this page">(.*?)</nav>', about, re.S).group(1)
    targets = re.findall(r'href="#([\w-]+)"', nav)
    assert targets == ["limitations", "affiliate-links", "other-shops", "data", "privacy", "support"]
    assert all(f'<h2 id="{t}">' in about for t in targets)
    assert 'smaller "Kindle" and "Audible" buttons' in about


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
    assert "Found something new? <a" in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "Support me with a coffee on Ko-fi →" in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'class="kofi-line"' not in (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert 'class="kofi-line"' not in (tmp_path / "404.html").read_text(encoding="utf-8")
    # The floating button replaced the footer's Ko-fi link.
    footer = (tmp_path / "index.html").read_text(encoding="utf-8").split('<footer class="site-footer">')[1]
    assert "Buy me a coffee" not in footer.split("</footer>")[0]


def test_books_and_music_have_their_own_pages(tmp_path):
    releases = sample.releases(TODAY)
    pages = render.build(releases, datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    assert "/books/" in pages and "/music/" in pages
    books = (tmp_path / "books" / "index.html").read_text(encoding="utf-8")
    assert '<h1>Books</h1>' in books and 'href="/books/horror/"' in books and "powered by Google" in books
    assert 'href="/books/" aria-current="page"' in books
    # every recent book once, even when it's in more than one genre
    recent_ids = {r.id for r in render.recent([r for r in releases if r.kind == "books"], TODAY).releases}
    assert len(re.findall(r'<li class="card" data-id=', books)) == len(recent_ids) > 0
    music = (tmp_path / "music" / "index.html").read_text(encoding="utf-8")
    assert "powered by Google" not in music and 'href="/music/rock/"' in music
    genre = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert 'href="/books/" aria-current="true"' in genre and '<a class="kicker" href="/books/">' in genre
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'aria-current' not in home.split("</nav>")[0] and '<a class="kind-link" href="/music/">' in home
    assert f"{config.SITE_URL}/books/</loc>" in (tmp_path / "sitemap.xml").read_text(encoding="utf-8")


def test_link_previews(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    genre = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert '<meta property="og:url" content="https://brand-new.matt-rarely-writes.co.uk/books/horror/">' in genre
    assert re.search(r'<meta property="og:image" content="https://brand-new\.matt-rarely-writes\.co\.uk'
                     r'/static/share\.png\?v=[0-9a-f]{8}">', genre)
    assert re.search(r'<meta property="og:description" content="New horror books: \d+ out (this week|in the last '
                     r'two weeks) and \d+ due over the next three months\.">', genre)
    assert '<meta name="twitter:card" content="summary_large_image">' in genre
    assert '<meta name="msvalidate.01" content="43876E90C7D03768DD371FD4A72AF166">' in genre
    assert (tmp_path / "static" / "share.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
    assert render.lower_name("Tech & AI") == "tech & AI"


def test_running_late_notice_is_in_every_page_but_hidden(tmp_path):
    generated = datetime(2026, 9, 25, 9, 49, tzinfo=UK)
    render.build(sample.releases(TODAY), generated, tmp_path, TODAY)
    for page in ("index.html", "books/index.html", "books/horror/index.html", "about/index.html"):
        html = (tmp_path / page).read_text(encoding="utf-8")
        m = re.search(r'<p class="stale" role="status" hidden data-generated="([^"]+)" data-stale-hours="(\d+)">', html)
        assert m and datetime.fromisoformat(m[1]) == generated and int(m[2]) == config.STALE_HOURS
        assert "last updated on Friday 25 September 2026 at 09:49 BST. The daily update is running late" in html


def test_icons_are_defined_once_and_support_is_a_landmark(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    html = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert html.count('<symbol id="icon-external"') == 1                     # drawn once...
    assert html.count('<use href="#icon-external"/>') > 5                     # ...used many times
    assert not re.search(r'<svg class="icon"[^>]*>(?:(?!</svg>).)*<path', html, re.S)  # icons only <use>
    assert re.search(r'<aside class="support" aria-label="Support Brand New">\s*(\{#.*?#\}\s*)?<a class="support-btn"',
                     html, re.S)


def test_home_screen_icons_and_manifest(tmp_path):
    import json
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<link rel="apple-touch-icon" href="/static/icon-180\.png\?v=[0-9a-f]{8}">', home)
    assert re.search(r'<link rel="manifest" href="/static/manifest\.webmanifest\?v=[0-9a-f]{8}">', home)
    manifest = json.loads((tmp_path / "static" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["short_name"] == "Brand New" and manifest["start_url"] == "/"
    for icon in manifest["icons"]:  # icon paths are relative to the manifest, in /static/
        png = (tmp_path / "static" / icon["src"]).read_bytes()
        size = int(icon["sizes"].split("x")[0])
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and int.from_bytes(png[16:20], "big") == size


def _ld(html: str) -> list:
    return [json.loads(m) for m in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)]


def test_sitemap_lastmod(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    sitemap = (tmp_path / "sitemap.xml").read_text(encoding="utf-8")
    assert f"<loc>{config.SITE_URL}/books/horror/</loc><lastmod>2026-09-25</lastmod>" in sitemap
    assert f"<loc>{config.SITE_URL}/about/</loc></url>" in sitemap


def test_structured_data(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = _ld((tmp_path / "index.html").read_text(encoding="utf-8"))
    assert home == [{"@context": "https://schema.org", "@type": "WebSite", "name": "Brand New",
                     "url": f"{config.SITE_URL}/"}]
    assert _ld((tmp_path / "about" / "index.html").read_text(encoding="utf-8")) == []

    genre = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    collection, crumbs = _ld(genre)[0]
    items = collection["mainEntity"]["itemListElement"]
    assert len(items) == collection["mainEntity"]["numberOfItems"] == genre.count('class="buy"')
    assert items[0]["position"] == 1 and items[0]["item"]["@type"] == "Book"
    assert items[0]["item"]["author"] == [{"@type": "Person", "name": "A. N. Author"}]
    assert [c["name"] for c in crumbs["itemListElement"]] == ["Brand New", "Books", "Horror"]
    assert crumbs["itemListElement"][2]["item"] == f"{config.SITE_URL}/books/horror/"

    rock = _ld((tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8"))[0]
    album = rock[0]["mainEntity"]["itemListElement"][0]["item"]
    assert album["@type"] == "MusicAlbum" and album["byArtist"]["@type"] == "MusicGroup"


def test_structured_data_cant_break_out_of_script():
    r = Release(kind="books", id="9780306406157", title="</script><script>alert(1)</script>", by="X, Y & Z",
                date=TODAY, source="test", amazon_url="https://www.amazon.co.uk/dp/0306406152", genres=["horror"])
    page = render.genre_page(BOOK_GENRES[3], [r], TODAY)
    text = str(render.json_ld(render.genre_ld(page)))
    assert "<" not in text and ">" not in text and "&" not in text
    item = json.loads(text)[0]["mainEntity"]["itemListElement"][0]["item"]
    assert item["name"] == r.title and [a["name"] for a in item["author"]] == ["X", "Y & Z"]


def test_tile_covers_prefer_releases_no_earlier_tile_used():
    def rel(i, genres, cover=True):
        return Release(kind="music", id=f"r{i}", title=f"R{i}", by="A", date=TODAY - timedelta(days=1),
                       source="test", amazon_url="", genres=genres, cover=f"https://x/{i}.jpg" if cover else None,
                       popularity=100 - i)
    releases = [rel(0, ["rock", "indie"]), rel(1, ["rock"]), rel(2, ["rock"]), rel(3, ["rock"]),
                rel(4, ["indie"]), rel(5, ["indie"], cover=False)]
    rock, indie = (render.genre_page(g, releases, TODAY) for g in config.MUSIC_GENRES if g.slug in ("rock", "indie"))
    render.pick_tile_covers([rock, indie])
    assert [r.id for r in rock.covers] == ["r0", "r1", "r2", "r3"]  # three shown, then a spare
    assert [r.id for r in indie.covers] == ["r4", "r0"]  # its own first; the shared one only to fill up


def test_tiles_show_a_cover_fan_or_the_kind_icon(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    fans = re.findall(r'<span class="tile-fan tile-fan-(books|music)" aria-hidden="true">(.*?)</span>', home, re.S)
    assert len(fans) == len(config.ALL_GENRES)
    for kind, fan in fans:
        imgs = fan.count("<img ")
        assert imgs <= 5 and (imgs or f'href="#icon-{kind}"' in fan)  # three shown, up to two spares
        assert imgs == fan.count('alt=""') == fan.count('referrerpolicy="no-referrer"')
    assert '<span class="tile-fan' in (tmp_path / "books" / "index.html").read_text(encoding="utf-8")


def test_countdown_stickers():
    days = {n: render.countdown(TODAY + timedelta(days=n), TODAY) for n in (-3, -2, -1, 0, 1, 2, 7, 8)}
    assert days == {-3: None, -2: "Just out", -1: "Just out", 0: "Out today!", 1: "Out tomorrow",
                    2: "2 days to go", 7: "7 days to go", 8: None}


def test_cards_get_stickers_and_albums_get_a_record(tmp_path):
    releases = [book(0, title="Today"), book(5, title="Soon"), book(30, title="Later"),
                Release(kind="music", id="m1", title="Album", by="A", date=TODAY, source="test", amazon_url="",
                        genres=["rock"], cover="https://x/1.jpg")]
    render.build(releases, datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    horror = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    cards = dict(re.findall(r'<li class="card" data-id="([^"]+)">(.*?)\n</li>', horror, re.S))
    assert '<span class="sticker" aria-hidden="true">Out today!</span>' in cards["Today"]
    assert "5 days to go" in cards["Soon"] and 'class="sticker"' not in cards["Later"]
    assert 'class="vinyl"' not in horror
    rock = (tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    assert rock.count('<span class="vinyl" aria-hidden="true"></span>') == rock.count('<li class="card"') == 1


def test_surprise_me_is_on_the_home_kind_and_genre_pages(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    for page, kind in (("index.html", ""), ("books/index.html", "books"), ("music/index.html", "music")):
        html = (tmp_path / page).read_text(encoding="utf-8")
        assert re.search(rf'<button class="surprise-btn" type="button" data-surprise="{kind}" hidden', html)
        assert '<div class="surprise" id="surprise" popover' in html
    horror = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<button class="surprise-btn" type="button" data-surprise="books" data-genre="horror" hidden\s+'
                     r'title="Pick a random horror book"', horror)
    assert (tmp_path / "data" / "releases.json").exists()  # what the button picks from


def test_every_book_card_has_a_made_up_cover_to_fall_back_on(tmp_path):
    no_cover = book(0, title="No Cover </b>")
    render.build([no_cover, book(1, title="Has Cover")], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    horror = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert horror.count('class="made-cover made-cover-books hue-') == horror.count('<li class="card"') == 2
    assert '<span class="mc-title">No Cover &lt;/b&gt;</span>' in horror  # escaped like any other text
    assert render.cover_hue(no_cover) == render.cover_hue(book(5, title="No Cover </b>"))  # same release, same colours
    assert len({render.cover_hue(book(0, title=str(i))) for i in range(50)}) == render.COVER_HUES


def test_albums_without_a_cover_show_just_the_record(tmp_path):
    album = Release(kind="music", id="m1", title="Album", by="A", date=TODAY, source="test", amazon_url="", genres=["rock"])
    render.build([album], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    rock = (tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    [card] = re.findall(r'<li class="card" data-id="m1">(.*?)\n</li>', rock, re.S)
    assert 'class="vinyl"' in card and "made-cover" not in card and "<img" not in card


def test_older_data_with_isbn_links_builds_with_searches(tmp_path):
    """Data saved when UK editions linked straight to an ISBN page gets search links, like fresh data."""
    from brandnew.__main__ import main
    old = {"kind": "books", "id": "9781529445282", "title": "The Thoroughbreds", "by": "Elin Hilderbrand",
           "date": TODAY.isoformat(), "source": "google-books", "publisher": "Hachette UK", "genres": ["horror"],
           "uk_edition": True, "amazon_url": "https://www.amazon.co.uk/dp/1529445280"}
    data = tmp_path / "r.json"
    data.write_text(json.dumps({"generated": "2026-09-25T05:00:00+01:00", "releases": [old]}), encoding="utf-8")
    assert main(["build", "--data", str(data), "--out", str(tmp_path / "dist")]) == 0
    html = (tmp_path / "dist" / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    assert "/dp/" not in html and not re.search(r'href="[^"]*9781529445282', html)  # no link by ISBN
    assert "https://www.amazon.co.uk/s?k=The+Thoroughbreds+Elin+Hilderbrand&amp;i=stripbooks&amp;tag=" in html
    assert 'href="https://uk.bookshop.org/search?keywords=The+Thoroughbreds+Elin+Hilderbrand"' in html


def test_about_page_says_every_link_is_a_search(tmp_path):
    render.build([], datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    about = (tmp_path / "about" / "index.html").read_text(encoding="utf-8")
    assert "Every link opens a search" in about and "straight to the book" not in about
    assert "Amazon Music included" in about and "—" not in about


def test_names():
    class S:
        def __init__(self, name): self.name = name
    assert render.names([]) == "" and render.names([S("A")]) == "A"
    assert render.names([S("A"), S("B")]) == "A and B" and render.names(map(S, "ABC")) == "A, B and C"


def test_streaming_links_for_upcoming_albums_come_after_record_shops(tmp_path):
    def album(days, title):
        return Release(kind="music", id=title, title=title, by="Band", date=TODAY + timedelta(days=days),
                       source="test", amazon_url="https://www.amazon.co.uk/s?k=x", genres=["rock"])
    render.build([album(0, "Out Today"), album(7, "Next Week")], datetime(2026, 9, 25, 5, 31, tzinfo=UK),
                 tmp_path, TODAY)
    html = (tmp_path / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    popovers = dict(re.findall(r'<strong>([^<]+)</strong><br>other places.*?</div>(.*?)</div>', html, re.S))
    headings = {t: re.findall(r'<p class="shops-group">([^<]+)</p>', p) for t, p in popovers.items()}
    assert headings == {"Out Today": ["Listen", "Record shops"], "Next Week": ["Record shops", "Listen"]}
    assert "Out on Fri 2 Oct 2026. Until then you may only find singles, or a pre-save." in popovers["Next Week"]
    assert "Out on" not in popovers["Out Today"]


def test_kindle_and_audible_are_small_buttons_under_the_amazon_one(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY, amazon_tag="test-21")
    html = (tmp_path / "books" / "horror" / "index.html").read_text(encoding="utf-8")
    rows = re.findall(r'</a>\s*<div class="amazon-formats" role="group" aria-label="Also on Amazon">(.*?)</div>', html, re.S)
    assert rows and len(rows) == html.count('class="buy"')
    for row in rows:
        links = re.findall(r'<a href="([^"]+)" rel="([^"]+)"[^>]*aria-label="Search Amazon UK[^"]*">(\w+)</a>', row)
        assert [text for _, _, text in links] == ["Kindle", "Audible"]
        assert all("tag=test-21" in href and rel == config.AFFILIATE_REL for href, rel, _ in links)


def test_about_styles_dont_leak_onto_the_genre_switcher():
    css = (render.STATIC / "style.css").read_text(encoding="utf-8")
    assert len(re.findall(r"^\.chips \{", css, re.M)) == 1  # the genre switcher's; About uses .shop-chips


def test_fonts_the_stylesheet_uses_are_hosted_here_with_their_licences():
    css = (render.STATIC / "style.css").read_text(encoding="utf-8")
    files = set(re.findall(r'url\("fonts/([^"]+)"\)', css))
    assert {"figtree-latin.woff2", "young-serif-latin.woff2", "dm-sans-600-latin.woff2"} <= files
    fonts = render.STATIC / "fonts"
    assert all((fonts / f).stat().st_size > 5000 for f in files)
    for name in ("figtree", "young-serif", "dm-sans"):
        assert "SIL Open Font License" in (fonts / f"OFL-{name}.txt").read_text(encoding="utf-8")


def test_every_tile_has_spare_covers_in_case_one_fails(tmp_path):
    """A cover host error (e.g. a Cover Art Archive 500) used to leave a fan of two."""
    def rel(kind, genre, i):
        return Release(kind=kind, id=f"{genre}{i}", title=f"T{i}", by="A", date=TODAY - timedelta(days=1), source="test",
                       amazon_url="", genres=[genre], cover=f"https://x/{genre}{i}.jpg", popularity=100 - i)
    releases = [rel(g.kind, g.slug, i) for g in config.ALL_GENRES for i in range(6)]
    render.build(releases, datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    home = (tmp_path / "index.html").read_text(encoding="utf-8")
    fans = re.findall(r'<span class="tile-fan tile-fan-(books|music)" aria-hidden="true">(.*?)</span>', home, re.S)
    assert {kind for kind, _ in fans} == {"books", "music"}
    assert all(fan.count("<img ") == 5 for _, fan in fans)
    css = (tmp_path / "static" / "style.css").read_text(encoding="utf-8")
    assert ".tile-fan img:nth-child(n+4) { display: none; }" in css
