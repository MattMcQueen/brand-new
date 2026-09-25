from brandnew import shops


def test_uk_edition_links_straight_to_the_book():
    links = dict(shops.book_links("9781405975735", "The Impossible Fortune", "Richard Osman", uk_edition=True))
    assert list(links) == ["Waterstones", "Bookshop.org", "Foyles", "Blackwell's", "Hive"]
    assert links["Bookshop.org"] == "https://uk.bookshop.org/book/9781405975735"
    assert links["Blackwell's"] == "https://blackwells.co.uk/bookshop/product/9781405975735"
    assert all("9781405975735" in url for url in links.values())


def test_other_editions_search_by_title_and_first_author():
    links = dict(shops.book_links("9780000000002", "Night: A Thriller", "Ann Author, Bob Writer", uk_edition=False))
    assert links["Waterstones"] == "https://www.waterstones.com/books/search/term/Night+Ann+Author"
    assert all("Night+Ann+Author" in url and "978" not in url for url in links.values())


def test_album_links_search_artist_and_title():
    links = dict(shops.album_links("Neil Young & The Chrome Hearts", "Second Song"))
    assert list(links) == ["HMV", "Rough Trade", "Norman Records", "Banquet Records", "Resident"]
    assert links["HMV"] == "https://hmv.com/search?searchtext=Neil+Young+%26+The+Chrome+Hearts+Second+Song"


def test_digital_links_are_searches_and_spotify_uses_a_path():
    links = dict(shops.digital_links("Night: A Thriller", "Ann Author, Bob Writer"))
    assert list(links) == ["Kobo", "Google Play Books", "Audible", "Spotify"]
    assert links["Kobo"] == "https://www.kobo.com/gb/en/search?query=Night+Ann+Author"
    assert links["Spotify"] == "https://open.spotify.com/search/Night%20Ann%20Author/audiobooks"


def test_groups_for_books_and_albums():
    books = shops.groups_for("books", "9781405975735", "T", "A", uk_edition=True)
    assert [g.heading for g in books] == ["Bookshops", "Ebooks & audiobooks"]
    assert books[1].note and all(formats for _, _, formats in books[1].links)
    assert [g.heading for g in shops.groups_for("music", "mbid", "T", "A", uk_edition=False)] == ["Record shops"]
