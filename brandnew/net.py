"""Polite fetching: a proper User-Agent, retries, and per-host rate limits."""
import json
import re
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from . import config

# Minimum seconds between requests to a host. MusicBrainz asks for at most 1 request per second.
MIN_INTERVAL = {"musicbrainz.org": 1.1, "api.listenbrainz.org": 0.5, "www.googleapis.com": 0.2}
_last: dict[str, float] = {}


class QuotaExhausted(RuntimeError):
    """The API's daily quota is used up: retrying is pointless until it resets."""


def _redact(url: str) -> str:
    return re.sub(r"key=[^&]+", "key=***", url)


def _wait_turn(host: str) -> None:
    gap = MIN_INTERVAL.get(host, 0)
    wait = _last.get(host, 0) + gap - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()


def _is_daily_quota(e: Exception) -> bool:
    """Google says 'Queries per day' in the body of a 429 when the daily quota is gone."""
    try:
        return "per day" in e.read().decode("utf-8", "replace").lower()
    except Exception:  # noqa: BLE001 - no readable body: treat it as an ordinary 429
        return False


def final_url(url: str, timeout: int = 20) -> str | None:
    """Where a link to a picture ends up after its redirects, or None if it doesn't end at a
    working picture. Only the headers are read: the picture itself isn't downloaded."""
    req = urllib.request.Request(url, headers={"User-Agent": config.USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            ok = r.status == 200 and r.headers.get_content_maintype() == "image"
            return r.geturl() if ok else None
    except (OSError, ValueError):  # URLError, HTTPError and timeouts are all OSErrors
        return None


def get_text(url: str, tries: int = 2, timeout: int = 60) -> str:
    """GET a web page as text (ISFDB pages are Latin-1). Raises RuntimeError after the last try."""
    return _get(url, None, tries, timeout, "text/html", lambda r: r.read().decode(
        r.headers.get_content_charset() or "iso-8859-1", "replace"))


def get_json(url: str, data: dict | list | None = None, tries: int = 4, timeout: int = 60):
    """GET (or POST when `data` is given) and parse JSON. Raises after the last failed try."""
    return _get(url, data, tries, timeout, "application/json", json.load)


def _get(url: str, data, tries: int, timeout: int, accept: str, read):
    host = urlsplit(url).hostname or ""
    headers = {"User-Agent": config.USER_AGENT, "Accept": accept}
    body = None
    if data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    for attempt in range(1, tries + 1):
        _wait_turn(host)
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return read(r)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            status = getattr(e, "code", None)
            if status == 429 and _is_daily_quota(e):
                raise QuotaExhausted(f"{_redact(url)[:100]}: daily quota used up") from None
            if attempt == tries or status in (400, 401, 403, 404):
                raise RuntimeError(f"{_redact(url)[:150]} failed: {e}") from None
            delay = 5 * attempt if status in (429, 503) else 2 * attempt
            print(f"  retrying {_redact(url)[:100]} in {delay}s ({e})", file=sys.stderr)
            time.sleep(delay)
