from brandnew import shops


def test_bookshops_search_by_title_and_first_author():
    links = dict(shops.book_links("Night: A Thriller", "Ann Author, Bob Writer"))
    assert list(links) == ["Waterstones", "Bookshop.org", "Foyles", "Blackwell's", "Hive"]
    assert links["Waterstones"] == "https://www.waterstones.com/books/search/term/Night+Ann+Author"
    assert links["Bookshop.org"] == "https://uk.bookshop.org/search?keywords=Night+Ann+Author"
    assert all("Night+Ann+Author" in url for url in links.values())


def test_album_links_search_artist_and_title():
    links = dict(shops.album_links("Neil Young & The Chrome Hearts", "Second Song"))
    assert list(links) == ["HMV", "Rough Trade", "Norman Records", "Banquet Records", "Resident"]
    assert links["HMV"] == "https://hmv.com/search?searchtext=Neil+Young+%26+The+Chrome+Hearts+Second+Song"


def test_digital_links_are_searches_and_spotify_uses_a_path():
    links = dict(shops.digital_links("Night: A Thriller", "Ann Author, Bob Writer"))
    assert list(links) == ["Kobo", "Google Play Books", "Spotify"]
    assert links["Kobo"] == "https://www.kobo.com/gb/en/search?query=Night+Ann+Author"
    assert links["Spotify"] == "https://open.spotify.com/search/Night%20Ann%20Author/audiobooks"


def test_groups_for_books_and_albums():
    books = shops.groups_for("books", "T", "A")
    assert [g.heading for g in books] == ["Bookshops", "Ebooks & audiobooks"]
    assert books[1].note and all(formats for _, _, formats in books[1].links)
    music = shops.groups_for("music", "T", "A")
    assert [g.heading for g in music] == ["Listen", "Record shops"] and not any(g.note for g in music)


def test_upcoming_album_puts_record_shops_first_with_a_dated_note():
    music = shops.groups_for("music", "T", "A", out_on="Fri 2 Oct 2026")
    assert [g.heading for g in music] == ["Record shops", "Listen"]
    assert music[1].note == "Out on Fri 2 Oct 2026. Until then you may only find singles, or a pre-save."
    assert not music[0].note


def test_listen_links_search_artist_and_title():
    links = dict(shops.listen_links("Neil Young & The Chrome Hearts", "Second Song"))
    assert list(links) == ["Spotify", "Apple Music", "YouTube Music", "Amazon Music", "Deezer", "Bandcamp"]
    assert links["Spotify"] == "https://open.spotify.com/search/Neil%20Young%20%26%20The%20Chrome%20Hearts%20Second%20Song/albums"
    assert links["Bandcamp"] == "https://bandcamp.com/search?q=Neil+Young+%26+The+Chrome+Hearts+Second+Song&item_type=a"

