"""Azure Static Web Apps settings (staticwebapp.config.json), written into the built site.

`brandnew serve` applies the same headers, so a local preview behaves like the live site.
"""
# Everything a page may load. Anything else (an injected script, a stray tracker) is blocked.
CSP = "; ".join([
    "default-src 'self'",
    # no inline scripts (see static/early.js); Cloudflare Web Analytics' counter script
    "script-src 'self' https://static.cloudflareinsights.com",
    "style-src 'self'",
    "font-src 'self'",
    # covers: our own copies of album covers ('self'), Google Books, and the Cover Art Archive (which
    # redirects to archive.org's servers) for albums we have no copy of
    "img-src 'self' https://books.google.com https://*.googleusercontent.com "
    "https://coverartarchive.org https://archive.org https://*.archive.org",
    "frame-src https://ko-fi.com",        # the Support me panel, only once it's opened
    "connect-src 'self' https://cloudflareinsights.com",  # where the counter sends page views
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "upgrade-insecure-requests",
])

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    "Strict-Transport-Security": "max-age=31536000",
}

# Pages change every morning, so browsers check back after 10 minutes. Files in /static/ are
# linked with a fingerprint of their contents (?v=...), so they can be kept for a year.
PAGE_CACHE = "public, max-age=600"
STATIC_CACHE = "public, max-age=31536000, immutable"


# Old page -> new page. "Science fiction & fantasy" was split in two; most of it was fantasy.
MOVED = {"/books/sf-fantasy": "/books/fantasy/"}  # the route covers it with or without a slash


def config() -> dict:
    return {
        # "auto": /books/horror -> /books/horror/, but files (style.css, robots.txt) are left alone;
        # "always" also redirected every file to a slashed address first.
        "trailingSlash": "auto",
        "routes": [
            {"route": "/static/*", "headers": {"Cache-Control": STATIC_CACHE}},
            # our copies of album covers: named after the Cover Art Archive's image ID, so never change
            {"route": "/covers/*", "headers": {"Cache-Control": STATIC_CACHE}},
            # Genre pages that moved: search engines and bookmarks still have the old address
            *({"route": f"{old}*", "redirect": new, "statusCode": 301} for old, new in MOVED.items()),
        ],
        "responseOverrides": {"404": {"rewrite": "/404.html"}},
        "globalHeaders": {**SECURITY_HEADERS, "Cache-Control": PAGE_CACHE},
        "mimeTypes": {".woff2": "font/woff2", ".json": "application/json",
                      ".webmanifest": "application/manifest+json"},
    }


def headers_for(path: str) -> dict:
    """The headers Azure would send for `path` (route headers win over global ones)."""
    cfg = config()
    headers = dict(cfg["globalHeaders"])
    for route in cfg["routes"]:
        prefix = route["route"].rstrip("*")
        if path.startswith(prefix):
            headers.update(route.get("headers", {}))
    return headers
