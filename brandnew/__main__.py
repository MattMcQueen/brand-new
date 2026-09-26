"""Command line: python -m brandnew fetch | build | serve"""
import argparse
import functools
import http.server
import os
import sys
from pathlib import Path

from . import config, hosting, pipeline, render, sample, store
from .sources import google_books, isfdb, listenbrainz
from .ukdates import now_uk

DEFAULT_DATA = Path(".cache/releases.json")
# Exit code for "the data is too thin to build from": the workflow treats it as a warning, not a failure.
TOO_FEW_RELEASES = 3
DEFAULT_OUT = Path("dist")
GENRE_CACHE = Path(".cache/artist-genres.json")
ISFDB_CACHE = Path(".cache/isfdb.json")


def fetch_books(today) -> list:
    """Google Books, plus science fiction, fantasy and horror from the ISFDB. The ISFDB is extra:
    if it fails, the books from Google Books still go ahead."""
    found = google_books.fetch(today)
    try:
        found += isfdb.fetch(today, ISFDB_CACHE)
    except Exception as e:  # noqa: BLE001 - any ISFDB problem just means fewer books today
        print(f"! ISFDB failed ({e}); carrying on without it", file=sys.stderr)
    return google_books.merge(found)


def cmd_fetch(args) -> int:
    now = now_uk()
    today = now.date()
    previous = []
    if args.previous:
        try:
            _, previous = store.load(args.previous)
            previous = google_books.relink(previous)
            print(f"Previous run: {len(previous)} releases from {args.previous}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001 - first run, or the site isn't live yet
            print(f"No previous data ({e}); carrying on without a fallback.", file=sys.stderr)
    sources = {"books": lambda: fetch_books(today),
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
        releases = google_books.relink(releases)  # so older data links the way fresh data would
        for kind in ("books", "music"):
            n = sum(r.kind == kind for r in releases)
            if n < args.min_releases:
                print(f"Only {n} {kind} releases (need {args.min_releases}); not building.", file=sys.stderr)
                return TOO_FEW_RELEASES
    tag = os.environ.get("AMAZON_TAG") or config.AMAZON_TAG
    pages = render.build(releases, generated, args.out, now.date(), amazon_tag=tag)
    print(f"Built {len(pages)} pages from {len(releases)} releases into {args.out}/",
          file=sys.stderr)
    return 0


class PreviewHandler(http.server.SimpleHTTPRequestHandler):
    """Serves dist/ like Azure will: the same headers, and the site's own 404 page."""

    def end_headers(self):
        for name, value in hosting.headers_for(self.path.split("?")[0]).items():
            if name != "Strict-Transport-Security":  # HTTPS only; this preview is plain HTTP
                self.send_header(name, value)
        super().end_headers()

    def send_error(self, code, message=None, explain=None):
        page = Path(self.directory) / "404.html"
        if code == 404 and page.exists():
            body = page.read_bytes()
            self.send_response(404)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().send_error(code, message, explain)


def cmd_serve(args) -> int:
    handler = functools.partial(PreviewHandler, directory=str(args.out))
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
    b.add_argument("--min-releases", type=int, default=0,
                   help="refuse to build if books or music has fewer releases than this")
    b.set_defaults(func=cmd_build)
    s = sub.add_parser("serve", help="preview dist/ locally")
    s.add_argument("--out", type=Path, default=DEFAULT_OUT)
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)
    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
