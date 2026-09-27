import json
import re
from datetime import datetime

from brandnew import config, hosting, render, sample
from test_render import TODAY, UK


def test_config_written_with_headers_caching_and_404(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    cfg = json.loads((tmp_path / "staticwebapp.config.json").read_text(encoding="utf-8"))
    assert cfg["responseOverrides"]["404"]["rewrite"] == "/404.html" and (tmp_path / "404.html").exists()
    assert "frame-src https://ko-fi.com" in cfg["globalHeaders"]["Content-Security-Policy"]
    assert hosting.headers_for("/static/style.css")["Cache-Control"].endswith("immutable")
    assert hosting.headers_for("/books/horror/")["Cache-Control"] == hosting.PAGE_CACHE


def test_pages_have_nothing_inline_that_the_policy_would_block(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    for page in tmp_path.rglob("*.html"):
        html = page.read_text(encoding="utf-8")
        assert "<script>" not in html, page                       # script-src 'self': files only
        assert not re.search(r"\son[a-z]+=", html), page           # no onerror=, onclick=...
        assert not re.search(r"\sstyle=", html), page              # style-src 'self'


def test_cover_hosts_are_allowed():
    csp = hosting.CSP
    for host in ("https://books.google.com", "https://coverartarchive.org", "https://*.archive.org"):
        assert host in csp


def test_files_are_not_redirected_to_slashed_addresses():
    assert hosting.config()["trailingSlash"] == "auto"


def test_old_sf_fantasy_page_redirects_to_fantasy():
    [route] = [r for r in hosting.config()["routes"] if "redirect" in r]
    assert route == {"route": "/books/sf-fantasy*", "redirect": "/books/fantasy/", "statusCode": 301}
    assert hosting.headers_for("/books/sf-fantasy/")["Cache-Control"] == hosting.PAGE_CACHE  # no headers of its own


def test_analytics_script_only_when_a_token_is_set(tmp_path, monkeypatch):
    when = datetime(2026, 9, 25, 5, 31, tzinfo=UK)
    monkeypatch.setattr(config, "CLOUDFLARE_ANALYTICS_TOKEN", "")
    render.build(sample.releases(TODAY), when, tmp_path / "off", TODAY)
    assert "cloudflareinsights" not in (tmp_path / "off" / "index.html").read_text(encoding="utf-8")
    monkeypatch.setattr(config, "CLOUDFLARE_ANALYTICS_TOKEN", "abc123")
    render.build(sample.releases(TODAY), when, tmp_path / "on", TODAY)
    for page in ("index.html", "about/index.html"):
        html = (tmp_path / "on" / page).read_text(encoding="utf-8")
        assert """data-cf-beacon='{"token": "abc123"}'""" in html, page
    assert "Cloudflare Web Analytics" in (tmp_path / "on" / "about" / "index.html").read_text(encoding="utf-8")


def test_analytics_hosts_are_allowed():
    assert "script-src 'self' https://static.cloudflareinsights.com" in hosting.CSP
    assert "connect-src 'self' https://cloudflareinsights.com" in hosting.CSP


def test_bluesky_handle_file(tmp_path):
    render.build(sample.releases(TODAY), datetime(2026, 9, 25, 5, 31, tzinfo=UK), tmp_path, TODAY)
    assert (tmp_path / ".well-known" / "atproto-did").read_text(encoding="utf-8") == config.BLUESKY_DID
    assert config.BLUESKY_DID.startswith("did:plc:")
    assert hosting.headers_for("/.well-known/atproto-did")["Content-Type"].startswith("text/plain")
