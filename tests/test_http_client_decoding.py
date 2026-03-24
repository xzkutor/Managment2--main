import gzip
from io import BytesIO
import requests

from pricewatch.net.http_client import HttpClient


class FakeSession:
    def __init__(self, compressed_bytes):
        self.compressed = compressed_bytes
        self.headers = {}

    def request(self, method, url, timeout=None, allow_redirects=True, **kwargs):
        resp = requests.models.Response()
        resp.status_code = 200
        resp.url = url
        resp._content = self.compressed
        resp.headers = {'Content-Encoding': 'gzip', 'Content-Type': 'text/html; charset=utf-8'}
        return resp


def test_safe_get_decodes_gzip(tmp_path):
    # prepare compressed gzip bytes
    original = b"<html><body>Hello GZIP</body></html>"
    compressed = gzip.compress(original)

    client = HttpClient(
        cache_dir=str(tmp_path),
        cache_ttl_seconds=86400,
        min_delay=0.0,
        max_delay=0.0,
        fast_mode=True,
        timeout=1,
        verbose=False,
    )
    # replace session with fake one
    client.session = FakeSession(compressed)

    resp = client.safe_get('https://example.com', use_cache=False, session=client.session)
    assert resp is not None
    # resp.content should be decoded and equal original
    assert resp.content == original
    # header Content-Encoding should have been removed by decoding step
    assert 'Content-Encoding' not in resp.headers

