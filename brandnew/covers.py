"""Album covers served from our own hosting, so they don't wait on the Internet Archive's servers
(some take many seconds to answer). Book covers stay on Google: its API terms don't allow keeping
copies, and they load quickly anyway.

Copies are kept in a folder the workflow carries from run to run (.cache/covers), named after the
Cover Art Archive's image ID, which never changes: a cover already there isn't downloaded again,
and one that no album in the data uses any more is deleted. The build publishes the ones in use
at /covers/. An album whose copy is missing keeps linking to the Internet Archive."""
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

from . import net
from .models import Release

SIZES = (250, 500)
MAX_BYTES = 2_000_000   # a 500-pixel cover is well under this; anything bigger isn't a normal cover
WORKERS = 8
URL_PATH = "/covers/"
# A Cover Art Archive link: release ID, then image ID, then size
CAA = re.compile(r"^https://coverartarchive\.org/release/([0-9a-f-]{36})/(\d+)-(?:250|500)\.jpg$")


def key(r: Release) -> str | None:
    """The name an album's cover is kept under (without the size), or None for anything that
    isn't an album with a Cover Art Archive cover."""
    if r.kind != "music":
        return None
    # direct_covers keeps the Cover Art Archive link as the backup when it links to a copy
    m = CAA.match(r.cover_backup or r.cover or "")
    return f"{m[1]}-{m[2]}" if m else None


def file_name(k: str, size: int) -> str:
    return f"{k}-{size}.jpg"


def _sources(r: Release, size: int) -> list[str]:
    """Where to download a size from: the Internet Archive copy direct_covers found (if any), then
    the Cover Art Archive link, which may send the request to another copy."""
    small = size == SIZES[0]
    urls = [r.cover if small else r.cover_2x]
    if r.cover_backup:
        urls.append(r.cover_backup if small else r.cover_backup.replace("-250.jpg", "-500.jpg"))
    return [u for u in dict.fromkeys(urls) if u]


def sync(releases: list[Release], folder: Path, download=net.get_jpeg) -> dict:
    """Bring `folder` in line with the albums in `releases`: download the covers it doesn't have
    yet, and delete the ones no album uses. Returns counts for the log."""
    folder.mkdir(parents=True, exist_ok=True)
    wanted: dict[str, list[str]] = {}
    for r in releases:
        k = key(r)
        if k:
            for size in SIZES:
                wanted.setdefault(file_name(k, size), _sources(r, size))
    have = {p.name for p in folder.glob("*.jpg")}
    todo = [name for name in wanted if name not in have]

    def fetch(name: str) -> bool:
        for url in wanted[name]:
            body = download(url, MAX_BYTES)
            if body:
                tmp = folder / (name + ".part")  # a run stopped mid-write leaves no half cover
                tmp.write_bytes(body)
                tmp.replace(folder / name)
                return True
        return False

    with ThreadPoolExecutor(WORKERS) as pool:
        got = sum(pool.map(fetch, todo))
    removed = 0
    for p in folder.iterdir():
        if p.name not in wanted:
            p.unlink()
            removed += 1
    stats = {"kept": len(wanted) - len(todo), "downloaded": got, "failed": len(todo) - got,
             "removed": removed, "mb": round(sum(p.stat().st_size for p in folder.glob("*.jpg")) / 1e6, 1)}
    print(f"  Album covers: {stats['kept']} already here, {got} downloaded, {stats['failed']} failed, "
          f"{removed} no longer used removed; {stats['mb']} MB", file=sys.stderr)
    return stats


def use_local(releases: list[Release], folder: Path) -> tuple[list[Release], set[str]]:
    """Point albums whose cover is in `folder` (both sizes) at our copy, keeping the Cover Art
    Archive link as the backup early.js falls back on. Returns the releases and the file names used."""
    out, used = [], set()
    for r in releases:
        k = key(r)
        names = [file_name(k, s) for s in SIZES] if k else []
        if names and all((folder / n).is_file() for n in names):
            backup = r.cover_backup or r.cover
            r = replace(r, cover=URL_PATH + names[0], cover_2x=URL_PATH + names[1], cover_backup=backup)
            used.update(names)
        out.append(r)
    return out, used


def publish(folder: Path, names: set[str], out: Path) -> None:
    """Copy the covers in use into the built site."""
    dest = out / URL_PATH.strip("/")
    dest.mkdir(parents=True, exist_ok=True)
    for n in names:
        (dest / n).write_bytes((folder / n).read_bytes())
