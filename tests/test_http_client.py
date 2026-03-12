import os
import time
from datetime import datetime, timedelta
import tempfile

import pytest

from pricewatch.net.http_client import HttpClient


def test_cache_age_and_mtime():
    # Prepare temporary cache directory and client
    with tempfile.TemporaryDirectory() as tmpdir:
        client = HttpClient(
            cache_dir=tmpdir,
            cache_max_age_days=30,
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

