import io
import urllib.error

import pytest

from brandnew import net


def http_error(code, body):
    return urllib.error.HTTPError("https://x.example/", code, "err", {}, io.BytesIO(body.encode()))


def test_daily_quota_stops_without_retrying(monkeypatch):
    calls = []

    def urlopen(req, timeout):
        calls.append(req)
        raise http_error(429, '{"error": {"message": "limit \'Queries per day\' of service books"}}')

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda s: pytest.fail("should not wait"))
    with pytest.raises(net.QuotaExhausted):
        net.get_json("https://x.example/?key=secret")
    assert len(calls) == 1


def test_per_minute_429_is_retried(monkeypatch):
    responses = [http_error(429, '{"error": {"message": "Queries per minute per user"}}')]

    class Ok(io.BytesIO):
        def __enter__(self): return self
        def __exit__(self, *a): pass

    def urlopen(req, timeout):
        if responses:
            raise responses.pop()
        return Ok(b'{"ok": true}')

    monkeypatch.setattr(net.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(net.time, "sleep", lambda s: None)
    assert net.get_json("https://x.example/") == {"ok": True}
