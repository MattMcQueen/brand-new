import json
from datetime import date, datetime, timedelta

import pytest

from brandnew import __main__ as cli
from brandnew import bluesky, config, sample, store
from brandnew.models import Release
from brandnew.ukdates import UK

FRIDAY = date(2026, 10, 2)
NOW = datetime(2026, 10, 2, 9, 30, tzinfo=UK)


def rel(kind="books", genre="horror", days=0, title="T", by="A", popularity=0, cover=None) -> Release:
    return Release(kind=kind, id=title, title=title, by=by, date=FRIDAY - timedelta(days=days),
                   source="test", amazon_url="https://www.amazon.co.uk/s?k=x", genres=[genre],
                   popularity=popularity, cover=cover)


def test_this_week_is_saturday_to_friday():
    week = bluesky.this_week([rel(days=d, title=str(d)) for d in (-1, 0, 6, 7)], FRIDAY)
    assert [r.title for r in week] == ["0", "6"]  # not tomorrow, not last Friday


def test_thread_opens_with_counts_then_a_reply_per_genre_in_site_order():
    posts = bluesky.thread(sample.releases(FRIDAY), FRIDAY)
    assert posts[0].text.startswith(f"{bluesky.OPENING}: 24 new books and 30 new albums")
    genres = [g for g in config.ALL_GENRES]
    assert len(posts) == 1 + len(genres)
    assert posts[1].text.startswith(f"{genres[0].name}, 3 new books:")
    assert posts[-1].card.url == f"{config.SITE_URL}/music/jazz/{bluesky.UTM}"
    assert all(len(p.text) <= bluesky.LIMIT for p in posts)


def test_quiet_genres_are_left_out_and_an_empty_week_posts_nothing():
    posts = bluesky.thread([rel(genre="horror"), rel(genre="romance", days=20)], FRIDAY)
    assert [p.text.split(",")[0] for p in posts[1:]] == ["Horror"]
    assert posts[0].tags == ["BookSky"]  # no music this week, so no #NewMusicFriday
    assert bluesky.thread([rel(days=20)], FRIDAY) == []


def test_links_go_to_our_pages_never_to_amazon():
    for p in bluesky.thread(sample.releases(FRIDAY), FRIDAY):
        assert p.card.url.startswith(config.SITE_URL) and "amazon" not in p.text.lower()


def test_highlights_most_listened_albums_and_books_with_covers():
    albums = [rel("music", "jazz", title="Quiet", popularity=5), rel("music", "jazz", title="Loud", popularity=900)]
    books = [rel(title="Bare", days=0), rel(title="Covered", days=3, cover="https://x/c.jpg")]
    assert "Loud by A; Quiet by A" in bluesky.genre_post(config.MUSIC_GENRES[-1], albums).text
    assert "Covered by A; Bare by A" in bluesky.genre_post(config.BOOK_GENRES[-1], books).text


def test_at_most_four_titles_then_and_n_more():
    text = bluesky.genre_post(config.BOOK_GENRES[-1], [rel(title=f"B{i}") for i in range(7)]).text
    assert text.count(" by A") == 4 and "; and 3 more" in text


def test_long_titles_still_fit():
    long = [rel(title="Word " * 80, by="Someone", cover="https://x/c.jpg"), rel(title="Other")]
    text = bluesky.genre_post(config.BOOK_GENRES[-1], long).text
    assert len(text) <= bluesky.LIMIT and "…; and 1 more" in text


@pytest.mark.parametrize("title, short", [
    ("Incarnate", "Incarnate"),
    ("King Zero: The New James Bond Novel", "King Zero"),
    ("The Demon’s Kiss (Demon Lovers, Book 1)", "The Demon’s Kiss"),
    ("(Untitled)", "(Untitled)"),  # nothing left after cutting: keep the whole title
])
def test_short_book_titles(title, short):
    assert bluesky.short_title(rel(title=title)) == short


def test_album_titles_are_left_alone():
    assert bluesky.short_title(rel("music", "rock", title="Ungebunden (curated)")) == "Ungebunden (curated)"


def test_hashtag_positions_are_in_bytes():
    text = "Sigil by Gåte 🧵\n\n#FolkMusic #NewMusicFriday"
    [folk, nmf] = bluesky.facets(text, ["FolkMusic", "NewMusicFriday"])
    raw = text.encode("utf-8")
    assert raw[folk["index"]["byteStart"]:folk["index"]["byteEnd"]] == b"#FolkMusic"
    assert raw[nmf["index"]["byteStart"]:nmf["index"]["byteEnd"]] == b"#NewMusicFriday"
    assert nmf["features"] == [{"$type": "app.bsky.richtext.facet#tag", "tag": "NewMusicFriday"}]


class FakeBluesky:
    """Stands in for Bluesky's API; `fail_at` makes the nth post fail."""

    def __init__(self, fail_at=None):
        self.records, self.fail_at = [], fail_at

    def __call__(self, method, url, body, headers):
        name = url.rsplit("/", 1)[-1]
        if name == "com.atproto.server.createSession":
            assert json.loads(body) == {"identifier": "bot.test", "password": "app-pw"}
            return {"did": "did:plc:bot", "handle": "bot.test", "accessJwt": "jwt"}
        assert headers["Authorization"] == "Bearer jwt"
        if name == "com.atproto.repo.uploadBlob":
            assert headers["Content-Type"] == "image/png" and body.startswith(b"\x89PNG")
            return {"blob": {"$type": "blob", "ref": {"$link": "img"}, "mimeType": "image/png", "size": len(body)}}
        if len(self.records) + 1 == self.fail_at:
            raise RuntimeError("Bluesky said 500")
        self.records.append(json.loads(body)["record"])
        n = len(self.records)
        return {"uri": f"at://did:plc:bot/app.bsky.feed.post/rkey{n}", "cid": f"cid{n}"}


def test_posts_a_thread_with_cards_tags_and_replies():
    fake = FakeBluesky()
    posts = bluesky.thread(sample.releases(FRIDAY), FRIDAY)
    links = bluesky.post_thread(posts, bluesky.Client("bot.test", "app-pw", fake), NOW)
    assert links[0] == "https://bsky.app/profile/bot.test/post/rkey1" and len(links) == len(posts)
    first, second, third = fake.records[:3]
    assert "reply" not in first and first["createdAt"] == "2026-10-02T08:30:00.000Z"  # BST -> UTC
    assert first["embed"]["external"]["thumb"]["ref"] == {"$link": "img"}
    assert first["facets"][0]["features"][0]["tag"] == "BookSky"
    assert second["reply"] == {"root": {"uri": "at://did:plc:bot/app.bsky.feed.post/rkey1", "cid": "cid1"},
                               "parent": {"uri": "at://did:plc:bot/app.bsky.feed.post/rkey1", "cid": "cid1"}}
    assert third["reply"]["root"]["cid"] == "cid1" and third["reply"]["parent"]["cid"] == "cid2"


def test_a_failure_halfway_says_what_was_posted():
    posts = bluesky.thread(sample.releases(FRIDAY), FRIDAY)
    with pytest.raises(RuntimeError, match=r"Posted 2 of 19:\nhttps://bsky.app/profile/bot.test/post/rkey1"):
        bluesky.post_thread(posts, bluesky.Client("bot.test", "app-pw", FakeBluesky(fail_at=3)), NOW)


def feed(*posts):
    return lambda url: {"feed": [{"post": {"record": {"text": t, "createdAt": when}}} for t, when in posts]}


def test_spots_todays_thread_already_posted():
    ours = f"{bluesky.OPENING}: 3 new books"
    assert bluesky.posted_today("bot.test", FRIDAY, feed((ours, "2026-10-02T08:30:00.000Z")))
    assert not bluesky.posted_today("bot.test", FRIDAY, feed((ours, "2026-09-25T08:30:00.000Z")))
    assert not bluesky.posted_today("bot.test", FRIDAY, feed(("Something else", "2026-10-02T08:30:00.000Z")))
    # 23:30 on Thursday in UTC is already Friday in the UK
    assert bluesky.posted_today("bot.test", FRIDAY, feed((ours, "2026-10-01T23:30:00.000Z")))


# --- The command's rules: when it posts, and when it won't ------------------------------------

@pytest.fixture
def data(tmp_path, monkeypatch):
    path = tmp_path / "releases.json"
    store.save(path, sample.releases(FRIDAY), NOW)
    monkeypatch.setattr(cli, "now_uk", lambda: NOW)
    monkeypatch.setenv("BLUESKY_HANDLE", "bot.test")
    monkeypatch.setenv("BLUESKY_APP_PASSWORD", "app-pw")
    sent = []
    monkeypatch.setattr(bluesky, "posted_today", lambda handle, today: False)
    monkeypatch.setattr(bluesky, "Client", lambda h, p: "client")
    monkeypatch.setattr(bluesky, "post_thread", lambda posts, client, now: sent.append(posts))
    return path, sent


def test_without_post_it_only_prints(data, capsys):
    path, sent = data
    assert cli.main(["bluesky", "--data", str(path)]) == 0
    assert "--- 1/19" in capsys.readouterr().out and sent == []


def test_posts_on_friday_from_todays_data(data):
    path, sent = data
    assert cli.main(["bluesky", "--data", str(path), "--post"]) == 0
    assert len(sent) == 1


def test_not_on_other_days_unless_told(data, monkeypatch):
    path, sent = data
    monkeypatch.setattr(cli, "now_uk", lambda: NOW + timedelta(days=1))
    store.save(path, sample.releases(FRIDAY), NOW + timedelta(days=1))
    assert cli.main(["bluesky", "--data", str(path), "--post"]) == 0 and sent == []
    assert cli.main(["bluesky", "--data", str(path), "--post", "--any-day"]) == 0 and len(sent) == 1


def test_not_from_old_data(data):
    path, sent = data
    store.save(path, sample.releases(FRIDAY), NOW - timedelta(days=1))
    assert cli.main(["bluesky", "--data", str(path), "--post"]) == 1 and sent == []


def test_not_twice(data, monkeypatch):
    path, sent = data
    monkeypatch.setattr(bluesky, "posted_today", lambda handle, today: True)
    assert cli.main(["bluesky", "--data", str(path), "--post"]) == 0 and sent == []


def test_not_without_credentials(data, monkeypatch):
    path, sent = data
    monkeypatch.delenv("BLUESKY_APP_PASSWORD")
    assert cli.main(["bluesky", "--data", str(path), "--post"]) == 1 and sent == []
