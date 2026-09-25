"""Command line: python -m brandnew fetch | build | serve"""
import argparse
import functools
import http.server
import os
import sys
from pathlib import Path

from . import pipeline, render, sample, store
from .sources import google_books, listenbrainz
from .ukdates import now_uk

DEFAULT_DATA = Path(".cache/releases.json")
DEFAULT_OUT = Path("dist")
GENRE_CACHE = Path(".cache/artist-genres.json")


def cmd_fetch(args) -> int:
    now = now_uk()
    today = now.date()
    previous = []
    if args.previous:
        try:
            _, previous = store.load(args.previous)
            print(f"Previous run: {len(previous)} releases from {args.previous}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - first run, or the site isn't live yet
            print(f"No previous data ({e}); carrying on without a fallback.", file=sys.stderr)
    sources = {"books": lambda: google_books.fetch(today),
               "music": lambda: listenbrainz.fetch(today, GENRE_CACHE)}
    releases = []
    for kind in ("books", "music"):
        if kind in sources and kind in args.only:
            print(f"Fetching {kind}...", file=sys.stderr)
            releases += pipeline.with_fallback(kind, sources[kind], previous, today)
        else:
            releases += [r for r in previous if r.kind == kind]
    store.save(args.data, releases, now)
    for kind in ("books", "music"):
        print(f"{kind}: {sum(r.kind == kind for r in releases)} releases", file=sys.stderr)
    print(f"Saved {args.data}", file=sys.stderr)
    return 0


def cmd_build(args) -> int:
    now = now_uk()
    if args.sample:
        generated, releases = now, sample.releases(now.date())
    else:
        if not args.data.exists():
            print(f"No data file at {args.data}. Use --sample to build with made-up data.", file=sys.stderr)
            return 1
        generated, releases = store.load(args.data)
    tag = os.environ.get("AMAZON_TAG") or None
    if not tag:
        print("Note: AMAZON_TAG is not set, so Amazon links have no tracking tag.", file=sys.stderr)
    pages = render.build(releases, generated, args.out, now.date(), amazon_tag=tag)
    print(f"Built {len(pages)} pages from {len(releases)} releases into {args.out}/", file=sys.stderr)
    return 0


def cmd_serve(args) -> int:
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(args.out))
    with http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"Serving {args.out}/ at http://localhost:{args.port}/ (Ctrl+C to stop)", file=sys.stderr)
        httpd.serve_forever()
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="brandnew")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch releases into the data file")
    f.add_argument("--data", type=Path, default=DEFAULT_DATA)
    f.add_argument("--previous", help="yesterday's data file or URL, used if a source fails")
    f.add_argument("--only", nargs="+", choices=["books", "music"], default=["books", "music"])
    f.set_defaults(func=cmd_fetch)
    b = sub.add_parser("build", help="render the site into dist/")
    b.add_argument("--data", type=Path, default=DEFAULT_DATA)
    b.add_argument("--out", type=Path, default=DEFAULT_OUT)
    b.add_argument("--sample", action="store_true", help="use made-up releases")
    b.set_defaults(func=cmd_build)
    s = sub.add_parser("serve", help="preview dist/ locally")
    s.add_argument("--out", type=Path, default=DEFAULT_OUT)
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
