from types import SimpleNamespace

import pytest

from modules import tvdb
from modules.util import Failed
from requests.exceptions import Timeout


def _response(status=200, content=b"<html><body>ok</body></html>", headers=None, reason="Mocked", url="https://www.thetvdb.com/test"):
    return SimpleNamespace(status_code=status, reason=reason, content=content, headers=headers or {}, url=url, history=[])


def _make_sequence_tvdb(sequence):
    calls = []

    def get_once(url, language=None):
        calls.append((url, language))
        value = sequence.pop(0)
        if isinstance(value, Exception):
            raise value
        return value

    instance = tvdb.TVDb(requests=SimpleNamespace(get_once=get_once), cache=None, tvdb_language="eng", expiration=60)
    return instance, calls


def _make_tvdb(response_status):
    """Build a TVDb instance whose underlying requests.get returns the chosen status."""
    fake_response = SimpleNamespace(
        status_code=response_status,
        reason="Mocked",
        content=b"<html></html>",
    )
    fake_requests = SimpleNamespace(get=lambda url, language=None: fake_response)
    return tvdb.TVDb(requests=fake_requests, cache=None, tvdb_language="eng", expiration=60)


def test_notfound_is_failed_subclass():
    # Callers that want to keep catching every TVDb failure as Failed should still work.
    assert issubclass(tvdb.NotFound, Failed)


def test_get_request_raises_notfound_on_4xx():
    t = _make_tvdb(404)
    with pytest.raises(tvdb.NotFound):
        t.get_request("https://www.thetvdb.com/dereferrer/series/463160")


def test_get_request_raises_failed_on_5xx(monkeypatch):
    # Suppress tenacity's wait so the 6-retry loop finishes instantly.
    monkeypatch.setattr("time.sleep", lambda _: None)
    t = _make_tvdb(503)
    with pytest.raises(Failed) as excinfo:
        t.get_request("https://www.thetvdb.com/dereferrer/series/81189")
    # Must not be the NotFound subclass — 5xx is treated as transient.
    assert not isinstance(excinfo.value, tvdb.NotFound)


def test_tvdbobj_init_propagates_notfound_for_stale_id():
    t = _make_tvdb(404)
    with pytest.raises(tvdb.NotFound) as excinfo:
        tvdb.TVDbObj(t, 463160, is_movie=False, ignore_cache=True)
    assert "463160" in str(excinfo.value)
    assert "No Series found" in str(excinfo.value)


def test_get_request_success():
    instance, calls = _make_sequence_tvdb([_response()])
    assert instance.get_request("https://www.thetvdb.com/test").xpath("//body/text()")[0] == "ok"
    assert len(calls) == 1


def test_get_request_429_uses_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr("modules.tvdb.time.sleep", sleeps.append)
    monkeypatch.setattr("modules.tvdb.random.uniform", lambda *_: 0)
    instance, _ = _make_sequence_tvdb([_response(429, headers={"Retry-After": "5"}), _response()])
    instance.get_request("https://www.thetvdb.com/test")
    assert sleeps == [5.0]


def test_get_request_503_backoff_then_success(monkeypatch):
    sleeps = []
    monkeypatch.setattr("modules.tvdb.time.sleep", sleeps.append)
    monkeypatch.setattr("modules.tvdb.random.uniform", lambda *_: 0)
    instance, _ = _make_sequence_tvdb([_response(503), _response()])
    instance.get_request("https://www.thetvdb.com/test")
    assert sleeps == [1]


def test_get_request_empty_200_exhausts_without_parser_error(monkeypatch):
    monkeypatch.setattr("modules.tvdb.time.sleep", lambda _: None)
    monkeypatch.setattr("modules.tvdb.random.uniform", lambda *_: 0)
    instance, _ = _make_sequence_tvdb([_response(content=b"")] * 4)
    with pytest.raises(tvdb.Unavailable, match="HTTP 200 with empty body"):
        instance.get_request("https://www.thetvdb.com/test")


def test_get_request_404_is_definitive_and_not_retried():
    instance, calls = _make_sequence_tvdb([_response(404)])
    with pytest.raises(tvdb.NotFound, match="resource does not exist"):
        instance.get_request("https://www.thetvdb.com/test")
    assert len(calls) == 1


def test_get_request_timeout_exhausts_cleanly(monkeypatch):
    monkeypatch.setattr("modules.tvdb.time.sleep", lambda _: None)
    monkeypatch.setattr("modules.tvdb.random.uniform", lambda *_: 0)
    instance, calls = _make_sequence_tvdb([Timeout("slow")] * 4)
    with pytest.raises(tvdb.Unavailable, match="Network failure"):
        instance.get_request("https://www.thetvdb.com/test")
    assert len(calls) == 4


def test_get_request_succeeds_on_third_attempt(monkeypatch):
    monkeypatch.setattr("modules.tvdb.time.sleep", lambda _: None)
    monkeypatch.setattr("modules.tvdb.random.uniform", lambda *_: 0)
    instance, calls = _make_sequence_tvdb([_response(503), _response(content=b""), _response()])
    assert instance.get_request("https://www.thetvdb.com/test") is not None
    assert len(calls) == 3
