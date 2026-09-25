import json
import re
from datetime import datetime

from brandnew import hosting, render, sample
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
