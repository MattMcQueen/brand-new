"""Command line: python -m brandnew build | serve"""
import argparse
import functools
import http.server
import os
import sys
from pathlib import Path

from . import render, sample, store
from .ukdates import now_uk

DEFAULT_DATA = Path(".cache/releases.json")
DEFAULT_OUT = Path("dist")


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
