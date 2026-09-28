import json
from datetime import datetime

from brandnew import __main__ as cli, config, covers, hosting, render
from brandnew.models import Release
from test_render import TODAY, UK

JPEG = b"\xff\xd8\xff\xe0 a cover"
RG = "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"  # a release ID, as the Cover Art Archive uses them


def caa(image_id, size=250):
    return f"https://coverartarchive.org/release/{RG}/{image_id}-{size}.jpg"


def ia(image_id, size=250):
    return f"https://ia800.us.archive.org/1/items/mbid-{RG}/mbid-{RG}-{image_id}_thumb{size}.jpg"


def album(image_id, direct=True, genres=("rock",)):
    """An album as the fetch leaves it: linked straight to an Internet Archive copy (direct_covers)
    with the Cover Art Archive link as the backup, or still on the Cover Art Archive."""
    if direct:
        cover, cover_2x, backup = ia(image_id), ia(image_id, 500), caa(image_id)
    else:
        cover, cover_2x, backup = caa(image_id), caa(image_id, 500), None
    return Release(kind="music", id=f"rg{image_id}", title=f"Album {image_id}", by="Band", date=TODAY,
                   source="listenbrainz", amazon_url="https://www.amazon.co.uk/s?k=x", genres=list(genres),
                   cover=cover, cover_2x=cover_2x, cover_backup=backup)


BOOK = Release(kind="books", id="9780000000001", title="Book", by="Author", date=TODAY, source="google-books",
               amazon_url="https://www.amazon.co.uk/dp/0000000001", genres=["horror"],
               cover="https://books.google.com/books/content?id=1&img=1&zoom=1&fife=w320")


def test_key_is_the_cover_art_archive_image_and_only_for_albums():
    assert covers.key(album(11)) == f"{RG}-11"
    assert covers.key(album(11, direct=False)) == f"{RG}-11"
    assert covers.key(BOOK) is None
    assert covers.key(Release(kind="music", id="x", title="T", by="B", date=TODAY, source="listenbrainz",
                              amazon_url="")) is None


def test_sync_downloads_only_whats_missing_and_removes_whats_unused(tmp_path):
    (tmp_path / f"{RG}-11-250.jpg").write_bytes(JPEG)   # already copied
    (tmp_path / f"{RG}-11-500.jpg").write_bytes(JPEG)
    (tmp_path / f"{RG}-99-250.jpg").write_bytes(JPEG)   # an album that's gone from the data
    asked = []

    def download(url, max_bytes):
        asked.append(url)
        return JPEG

    stats = covers.sync([album(11), album(12), BOOK], tmp_path, download)
    assert asked == [ia(12), ia(12, 500)]  # nothing for the album already copied, or the book
    assert sorted(p.name for p in tmp_path.iterdir()) == [f"{RG}-{i}-{s}.jpg" for i in (11, 12) for s in (250, 500)]
    assert stats | {"mb": 0} == {"kept": 2, "downloaded": 2, "failed": 0, "removed": 1, "mb": 0}


def test_sync_falls_back_to_the_cover_art_archive_and_keeps_nothing_that_failed(tmp_path):
    answers = {ia(12): None, caa(12): JPEG,     # the Internet Archive copy fails; the CAA link works
               ia(12, 500): None, caa(12, 500): None,   # neither works
               caa(13): None, caa(13, 500): None}

    stats = covers.sync([album(12), album(13, direct=False)], tmp_path, lambda url, _: answers[url])
    assert [p.name for p in tmp_path.iterdir()] == [f"{RG}-12-250.jpg"]
    assert stats["downloaded"] == 1 and stats["failed"] == 3


def test_use_local_needs_both_sizes_and_keeps_the_caa_link_as_backup(tmp_path):
    for name in (f"{RG}-11-250.jpg", f"{RG}-11-500.jpg", f"{RG}-12-250.jpg"):
        (tmp_path / name).write_bytes(JPEG)
    out, used = covers.use_local([album(11), album(12), BOOK], tmp_path)
    assert out[0].cover == f"/covers/{RG}-11-250.jpg" and out[0].cover_2x == f"/covers/{RG}-11-500.jpg"
    assert out[0].cover_backup == caa(11)
    assert out[1] == album(12)  # only one size copied: stays on the Internet Archive
    assert out[2] is BOOK
    assert used == {f"{RG}-11-250.jpg", f"{RG}-11-500.jpg"}


def test_build_serves_copied_covers_and_publishes_only_those_in_use(tmp_path, monkeypatch):
    data, store_dir, out = tmp_path / "releases.json", tmp_path / "covers", tmp_path / "dist"
    from brandnew import store
    store.save(data, [album(11), album(12), BOOK], datetime(2026, 9, 28, 9, 18, tzinfo=UK))
    store_dir.mkdir()
    for name in (f"{RG}-11-250.jpg", f"{RG}-11-500.jpg"):
        (store_dir / name).write_bytes(JPEG)
    monkeypatch.setattr(cli, "now_uk", lambda: datetime(2026, 9, 28, 9, 30, tzinfo=UK))
    assert cli.main(["build", "--data", str(data), "--out", str(out), "--covers", str(store_dir)]) == 0

    assert sorted(p.name for p in (out / "covers").iterdir()) == [f"{RG}-11-250.jpg", f"{RG}-11-500.jpg"]
    page = (out / "music" / "rock" / "index.html").read_text(encoding="utf-8")
    assert f'src="/covers/{RG}-11-250.jpg"' in page and f'data-backup="{caa(11)}"' in page
    assert f'src="{ia(12)}"' in page  # no copy yet: linked as before
    # "Surprise me" reads the published data, so it gets our copies too, and the books are untouched
    published = {r["id"]: r for r in json.loads((out / "data" / "releases.json").read_text(encoding="utf-8"))["releases"]}
    assert published["rg11"]["cover"] == f"/covers/{RG}-11-250.jpg"
    assert published[BOOK.id]["cover"] == BOOK.cover
    # structured data needs a full address
    assert f'"image":"{config.SITE_URL}/covers/{RG}-11-250.jpg"' in page
    # the data kept for the next run still has the original links
    assert store.load(data)[1][0].cover == ia(11)


def test_copied_covers_are_cached_like_static_files():
    assert hosting.headers_for(f"/covers/{RG}-11-250.jpg")["Cache-Control"] == hosting.STATIC_CACHE
