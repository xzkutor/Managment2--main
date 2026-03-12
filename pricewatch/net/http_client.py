import os
import time
import random
import hashlib
import requests
import logging
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


class HttpClient:
    DEFAULT_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'uk-UA,uk;q=0.9,en;q=0.8',
        'Referer': 'https://www.google.com/',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

    def __init__(
        self,
        cache_dir,
        cache_max_age_days,
        min_delay,
        max_delay,
        fast_mode,
        timeout=15,
        verbose=True,
        headers=None,
        session=None,
    ):
        self.cache_dir = cache_dir
        self.cache_max_age_days = int(cache_max_age_days)
        self.min_delay = float(min_delay)
        self.max_delay = float(max_delay)
        self.fast_mode = bool(fast_mode)
        self.timeout = float(timeout)
        self.verbose = bool(verbose)
        self.headers = headers.copy() if headers else self.DEFAULT_HEADERS.copy()
        self.session = session or self.create_session()
        self.session._client = self

    def create_session(self):
        sess = requests.Session()
        sess.headers.update(self.headers)
        from requests.adapters import HTTPAdapter
        from urllib3.util import Retry
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        adapter = HTTPAdapter(max_retries=retries)
        sess.mount('http://', adapter)
        sess.mount('https://', adapter)
        return sess

    def _get_cache_path(self, url):
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(self.cache_dir, f"{url_hash}.cache")

    def _is_cache_valid(self, cache_path):
        if not os.path.exists(cache_path):
            return False
        file_age_seconds = time.time() - os.path.getmtime(cache_path)
        max_age_seconds = self.cache_max_age_days * 24 * 60 * 60
        return file_age_seconds < max_age_seconds

    def _load_from_cache(self, cache_path):
        try:
            with open(cache_path, 'rb') as f:
                return f.read()
        except Exception as exc:
            if self.verbose:
                logger.warning("Failed to load cache from %s: %s", cache_path, exc)
            return None

    def _save_to_cache(self, cache_path, content):
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            with open(cache_path, 'wb') as f:
                f.write(content)
        except Exception as exc:
            if self.verbose:
                logger.warning("Failed to save cache to %s: %s", cache_path, exc)

    def _log(self, message):
        if self.verbose:
            logger.info(message)

    def get_cache_mtime(self, url, as_datetime=False):
        """
        Return the last modification time (save time) of the cache file for the given URL.

        Args:
            url (str): URL for which to look up the cache file.
            as_datetime (bool): if True return a datetime.datetime, otherwise a float (POSIX timestamp).

        Returns:
            float|datetime.datetime|None: modification time or None if the cache is missing.
        """
        cache_path = self._get_cache_path(url)
        if not os.path.exists(cache_path):
            return None
        try:
            mtime = os.path.getmtime(cache_path)
        except OSError:
            return None
        if as_datetime:
            return datetime.fromtimestamp(mtime)
        return mtime

    def _human_readable_age(self, seconds):
        """Convert seconds to a human readable age like '2 days, 3 hours ago'."""
        seconds = int(round(seconds))
        if seconds <= 0:
            return 'just now'
        parts = []
        days, rem = divmod(seconds, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, secs = divmod(rem, 60)
        if days:
            parts.append(f"{days} {'day' if days == 1 else 'days'}")
        if hours:
            parts.append(f"{hours} {'hour' if hours == 1 else 'hours'}")
        if minutes and not parts:
            # only include minutes if no days/hours (to keep it compact)
            parts.append(f"{minutes} {'minute' if minutes == 1 else 'minutes'}")
        if not parts and secs:
            parts.append(f"{secs} {'second' if secs == 1 else 'seconds'}")
        # show up to two largest parts
        display = ', '.join(parts[:2])
        return f"{display} ago"

    def get_cache_age(self, url, as_timedelta=False, human_readable=True):
        """
        Return the age of the cached file for a URL.

        Args:
            url (str): URL for which to compute cache age.
            as_timedelta (bool): if True return a datetime.timedelta. Mutually compatible with human_readable.
            human_readable (bool): if True return a human-readable string (e.g. '3 hours ago'). If False and as_timedelta is False, return age in seconds (float).

        Returns:
            str|datetime.timedelta|float|None: age representation or None if cache is missing.
        """
        mtime = self.get_cache_mtime(url, as_datetime=False)
        if mtime is None:
            return None
        age_seconds = time.time() - mtime
        if as_timedelta:
            return timedelta(seconds=age_seconds)
        if human_readable:
            return self._human_readable_age(age_seconds)
        return age_seconds

    def safe_get(self, url, method='GET', use_cache=True, session=None, **kwargs):
        session = session or self.session
        cache_path = None
        if method.upper() == 'GET' and use_cache:
            cache_path = self._get_cache_path(url)
            if self._is_cache_valid(cache_path):
                cached_content = self._load_from_cache(cache_path)
                if cached_content:
                    from requests.models import Response
                    resp = Response()
                    resp.status_code = 200
                    resp._content = cached_content
                    resp.url = url
                    resp.headers['Content-Type'] = 'text/html; charset=utf-8'
                    self._log(f"--> {method} {url} (from cache)")
                    return resp

        self._log(f"--> {method} {url}")
        if self.verbose:
            self._log(f"    headers: {session.headers}")
            if 'params' in kwargs:
                self._log(f"    params: {kwargs['params']}")
            if 'data' in kwargs or 'json' in kwargs:
                self._log(f"    body: {kwargs.get('data') or kwargs.get('json')}")
        try:
            resp = session.request(
                method,
                url,
                timeout=self.timeout,
                allow_redirects=True,
                **kwargs,
            )
            self._log(f"<-- status {resp.status_code} for {url}")
            if resp.status_code in (400, 403, 429):
                if self.verbose:
                    txt = resp.text[:1000].replace('\n', ' ')
                    self._log(f"    response text: {txt}")
                return None

            # Ensure compressed responses are decoded (gzip/deflate/br) before caching/returning.
            try:
                ce = (resp.headers.get('Content-Encoding') or '').lower()
                if ce:
                    # brotli
                    if 'br' in ce:
                        try:
                            import brotli

                            decoded = brotli.decompress(resp.content)
                            resp._content = decoded
                            resp.headers.pop('Content-Encoding', None)
                            self._log('    decoded brotli content')
                        except Exception as e:
                            self._log(f'    brotli decode failed: {e}')
                    # gzip
                    elif 'gzip' in ce or 'x-gzip' in ce:
                        try:
                            import gzip
                            from io import BytesIO

                            buf = BytesIO(resp.content)
                            with gzip.GzipFile(fileobj=buf) as f:
                                decoded = f.read()
                            resp._content = decoded
                            resp.headers.pop('Content-Encoding', None)
                            self._log('    decoded gzip content')
                        except Exception as e:
                            self._log(f'    gzip decode failed: {e}')
                    # deflate
                    elif 'deflate' in ce:
                        try:
                            import zlib

                            try:
                                decoded = zlib.decompress(resp.content)
                            except Exception:
                                # raw deflate stream fallback
                                decoded = zlib.decompress(resp.content, -zlib.MAX_WBITS)
                            resp._content = decoded
                            resp.headers.pop('Content-Encoding', None)
                            self._log('    decoded deflate content')
                        except Exception as e:
                            self._log(f'    deflate decode failed: {e}')
            except Exception as e:
                self._log(f'    content decoding unexpected error: {e}')

            if method.upper() == 'GET' and use_cache and resp.status_code == 200 and cache_path:
                self._save_to_cache(cache_path, resp.content)

            if not self.fast_mode:
                delay = random.uniform(self.min_delay, self.max_delay)
                time.sleep(delay)
            return resp
        except Exception as exc:
            if self.verbose:
                self._log(f"Request failed for {url}: {exc}")
            return None


def make_default_client():
    cache_dir = os.getenv('PARSER_CACHE_DIR', 'page_cache')
    cache_max_age_days = int(os.getenv('PARSER_CACHE_MAX_AGE_DAYS', '30'))
    fast_mode = os.getenv('PARSER_FAST', '').lower() in ('1', 'true', 'yes')
    return HttpClient(
        cache_dir=cache_dir,
        cache_max_age_days=cache_max_age_days,
        min_delay=1.0,
        max_delay=2.0,
        fast_mode=fast_mode,
        timeout=15,
        verbose=True,
    )


default_client = make_default_client()

__all__ = ["HttpClient", "make_default_client", "default_client"]

