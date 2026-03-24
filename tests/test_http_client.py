import os
import time
from datetime import datetime, timedelta
import tempfile


from pricewatch.net.http_client import HttpClient, _resolve_cache_ttl


def test_default_ttl_resolves_to_300(monkeypatch):
    """Default effective TTL must be 300 s when no env vars are set."""
    monkeypatch.delenv("PARSER_CACHE_TTL_SECONDS", raising=False)
    monkeypatch.delenv("PARSER_CACHE_MAX_AGE_DAYS", raising=False)
    assert _resolve_cache_ttl() == 300


def test_parser_cache_ttl_seconds_takes_precedence(monkeypatch):
    """PARSER_CACHE_TTL_SECONDS overrides PARSER_CACHE_MAX_AGE_DAYS."""
    monkeypatch.setenv("PARSER_CACHE_TTL_SECONDS", "120")
    monkeypatch.setenv("PARSER_CACHE_MAX_AGE_DAYS", "10")
    assert _resolve_cache_ttl() == 120


def test_deprecated_days_fallback(monkeypatch):
    """PARSER_CACHE_MAX_AGE_DAYS × 86400 is used when TTL_SECONDS is absent."""
    monkeypatch.delenv("PARSER_CACHE_TTL_SECONDS", raising=False)
    monkeypatch.setenv("PARSER_CACHE_MAX_AGE_DAYS", "2")
    assert _resolve_cache_ttl() == 2 * 86400


def test_cache_age_and_mtime():
    # Prepare temporary cache directory and client
    with tempfile.TemporaryDirectory() as tmpdir:
        client = HttpClient(
            cache_dir=tmpdir,
            cache_ttl_seconds=30 * 86400,
            min_delay=0.0,
            max_delay=0.0,
            fast_mode=True,
            timeout=1,
            verbose=False,
        )

        url = 'https://example.com/test'
        cache_path = client._get_cache_path(url)

        # Create cache file and set its mtime to a known value: 1 day, 1 hour, 1 minute, 1 second ago
        age_seconds = 1 * 86400 + 1 * 3600 + 1 * 60 + 1
        mtime = time.time() - age_seconds
        with open(cache_path, 'wb') as f:
            f.write(b"cached content")
        # set both atime and mtime
        os.utime(cache_path, (mtime, mtime))

        # Human readable
        hr = client.get_cache_age(url, human_readable=True)
        assert isinstance(hr, str)
        assert hr.endswith(' ago')
        # Expect the two largest parts: '1 day, 1 hour ago'
        assert hr.startswith('1 day') and '1 hour' in hr

        # timedelta
        td = client.get_cache_age(url, as_timedelta=True)
        assert isinstance(td, timedelta)
        assert abs(td.total_seconds() - age_seconds) < 2

        # numeric seconds
        sec = client.get_cache_age(url, as_timedelta=False, human_readable=False)
        assert isinstance(sec, float)
        assert abs(sec - age_seconds) < 2

        # get_cache_mtime with datetime
        mdt = client.get_cache_mtime(url, as_datetime=True)
        assert isinstance(mdt, datetime)
        assert abs(mdt.timestamp() - mtime) < 2

        # Missing cache -> None
        missing = client.get_cache_age('https://no-such.example', human_readable=True)
        assert missing is None
        assert client.get_cache_mtime('https://no-such.example') is None

