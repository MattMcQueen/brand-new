from datetime import date, timedelta

from brandnew.sources import listenbrainz as lb

TODAY = date(2026, 9, 25)


def feed_item(name="Album", artist="Band", days=0, primary="Album", secondary=None, caa=1, rg="rg1", tags=()):
    return {"artist_credit_name": artist, "artist_mbids": ["a-" + artist], "caa_id": caa,
            "caa_release_mbid": "rel-" + rg, "release_date": (TODAY + timedelta(days=days)).isoformat(),
            "release_group_mbid": rg, "release_group_primary_type": primary,
            "release_group_secondary_type": secondary, "release_name": name, "release_tags": list(tags)}


def test_base_title():
    assert lb.base_title("Hello (Deluxe Edition)") == "hello"
    assert lb.base_title("Hello [Explicit]") == "hello"
    assert lb.base_title("Hello - Deluxe Version") == "hello"
    assert lb.base_title("Hello - Goodbye") == "hello - goodbye"


def test_feed_filtering():
    items = [
        feed_item("Keep", rg="1"),
        feed_item("Single", primary="Single", rg="2"),
        feed_item("Hits", secondary="Compilation", rg="3"),
        feed_item("Live at X", secondary="Live", rg="4"),
        feed_item("Old (2026 Remaster)", rg="5"),
        feed_item("Big Night (Live at Wembley)", rg="9"),
        feed_item("Too old", days=-15, rg="6"),
        feed_item("Too far", days=91, rg="7"),
        dict(feed_item("Year only", rg="8"), release_date="2026"),
    ]
    names = sorted(a["release_name"] for a in lb.albums_from_feed(items, TODAY))
    assert names == ["Keep"]


def test_editions_are_merged_preferring_cover_then_earliest():
    items = [feed_item("Big (Deluxe)", days=3, rg="d"), feed_item("Big", days=5, rg="s"),
             feed_item("Big (Vinyl)", days=1, caa=None, rg="v")]
    [a] = lb.albums_from_feed(items, TODAY)
    assert a["release_group_mbid"] == "d"


def test_match_genres():
    assert lb.match_genres(["indie rock", "alternative"]) == ["rock", "indie"]
    assert lb.match_genres(["hip-hop"]) == ["hip-hop"]
    assert lb.match_genres(["trip hop"]) == []
    assert lb.match_genres(["metalcore"]) == ["metal"]
    assert lb.match_genres(["krautrock"]) == []
    assert lb.match_genres(["contemporary country", "country pop"]) == ["pop", "country"]
    assert lb.match_genres(["alternative country", "americana"]) == ["country"]
    assert lb.match_genres(["contemporary r&b", "neo soul"]) == ["rnb-soul"]
    assert lb.match_genres(["soulful house"]) == []


def test_to_release():
    a = dict(feed_item("Album", tags=["Jazz"]), date=TODAY)
    r = lb.to_release(a, ["jazz", "soul"], 900)
    assert r.genres == ["rnb-soul", "jazz"] and r.tags == ["jazz", "soul"] and r.popularity == 900
    assert r.cover == "https://coverartarchive.org/release/rel-rg1/1-250.jpg"
    assert r.amazon_url == "https://www.amazon.co.uk/s?k=Band+Album&i=popular"
    assert lb.to_release(a | {"release_tags": []}, ["polka"], 900) is None
    assert lb.to_release(a | {"release_tags": []}, ["polka", "a", "b", "jazz"], 900) is None  # 4th genre ignored


def test_cap_per_genre():
    albums = [lb.to_release(dict(feed_item(f"A{i}", rg=f"r{i}"), date=TODAY), ["rock"], i) for i in range(5)]
    albums.append(lb.to_release(dict(feed_item("J", rg="j"), date=TODAY), ["rock", "jazz"], 0))
    kept = lb.cap_per_genre(albums, limit=2)
    assert sorted(r.id for r in kept) == ["j", "r3", "r4"]
    assert next(r for r in kept if r.id == "j").genres == ["jazz"]


def test_genre_cache(tmp_path):
    path = tmp_path / "g.json"
    c = lb.GenreCache(path, TODAY)
    c.put("x", ["rock"])
    c.save()
    assert lb.GenreCache(path, TODAY).get("x") == ["rock"]
    assert lb.GenreCache(path, TODAY + timedelta(days=31)).get("x") is None
