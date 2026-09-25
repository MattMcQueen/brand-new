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
