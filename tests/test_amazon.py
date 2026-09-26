from brandnew import amazon


def test_book_url_searches_title_and_first_author():
    assert amazon.book_url("Big Book: A Novel", "Ann Author, Bo B") == \
        "https://www.amazon.co.uk/s?k=Big+Book+Ann+Author&i=stripbooks"


def test_music_url():
    assert amazon.music_url("Blur", "The Ballad") == "https://www.amazon.co.uk/s?k=Blur+The+Ballad&i=popular"


def test_with_tag():
    assert amazon.with_tag("https://www.amazon.co.uk/dp/0306406152", "abc-21") == \
        "https://www.amazon.co.uk/dp/0306406152?tag=abc-21"
    assert amazon.with_tag("https://www.amazon.co.uk/s?k=x&i=popular&tag=old-21", "abc-21") == \
        "https://www.amazon.co.uk/s?k=x&i=popular&tag=abc-21"
    assert amazon.with_tag("https://www.amazon.co.uk/dp/0306406152", None) == "https://www.amazon.co.uk/dp/0306406152"


def test_kindle_and_audible_searches():
    from brandnew import amazon
    assert amazon.kindle_url("Night: A Thriller", "Ann Author, Bob") == \
        "https://www.amazon.co.uk/s?k=Night+Ann+Author&i=digital-text"
    assert amazon.audible_url("Night", "Ann Author") == "https://www.amazon.co.uk/s?k=Night+Ann+Author&i=audible"
