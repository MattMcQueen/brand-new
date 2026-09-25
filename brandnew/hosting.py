"""Azure Static Web Apps settings (staticwebapp.config.json), written into the built site.

`brandnew serve` applies the same headers, so a local preview behaves like the live site.
"""
# Everything a page may load. Anything else (an injected script, a stray tracker) is blocked.
CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",                  # no inline scripts: see static/early.js
    "style-src 'self'",
    "font-src 'self'",
    # covers: Google Books, and the Cover Art Archive, which redirects to archive.org's servers
    "img-src 'self' https://books.google.com https://*.googleusercontent.com "
    "https://coverartarchive.org https://archive.org https://*.archive.org",
    "frame-src https://ko-fi.com",        # the Support me panel, only once it's opened
    "connect-src 'self'",
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


def config() -> dict:
    return {
        "trailingSlash": "always",
        "routes": [
            {"route": "/static/*", "headers": {"Cache-Control": STATIC_CACHE}},
        ],
        "responseOverrides": {"404": {"rewrite": "/404.html"}},
        "globalHeaders": {**SECURITY_HEADERS, "Cache-Control": PAGE_CACHE},
        "mimeTypes": {".woff2": "font/woff2", ".json": "application/json"},
    }


def headers_for(path: str) -> dict:
    """The headers Azure would send for `path` (route headers win over global ones)."""
    cfg = config()
    headers = dict(cfg["globalHeaders"])
    for route in cfg["routes"]:
        prefix = route["route"].rstrip("*")
        if path.startswith(prefix):
            headers.update(route["headers"])
    return headers
