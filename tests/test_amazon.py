from brandnew import amazon


def test_isbn13_to_10():
    assert amazon.isbn13_to_10("9780306406157") == "0306406152"
    assert amazon.isbn13_to_10("9780804429573") == "080442957X"  # check digit 10 -> X


def test_isbn13_to_10_rejects_979_and_junk():
    assert amazon.isbn13_to_10("9791234567896") is None
    assert amazon.isbn13_to_10("978030640615") is None
    assert amazon.isbn13_to_10(None) is None


def test_book_url_direct_and_search():
    assert amazon.book_url("9780306406157", "T", "A") == "https://www.amazon.co.uk/dp/0306406152"
    assert amazon.book_url("9791234567896", "T", "A") == "https://www.amazon.co.uk/s?k=9791234567896&i=stripbooks"
    assert amazon.book_url(None, "Big Book", "Ann Author") == "https://www.amazon.co.uk/s?k=Big+Book+Ann+Author&i=stripbooks"


def test_music_url():
    assert amazon.music_url("Blur", "The Ballad") == "https://www.amazon.co.uk/s?k=Blur+The+Ballad&i=popular"


def test_with_tag():
    assert amazon.with_tag("https://www.amazon.co.uk/dp/0306406152", "abc-21") == \
        "https://www.amazon.co.uk/dp/0306406152?tag=abc-21"
    assert amazon.with_tag("https://www.amazon.co.uk/s?k=x&i=popular&tag=old-21", "abc-21") == \
        "https://www.amazon.co.uk/s?k=x&i=popular&tag=abc-21"
    assert amazon.with_tag("https://www.amazon.co.uk/dp/0306406152", None) == "https://www.amazon.co.uk/dp/0306406152"
