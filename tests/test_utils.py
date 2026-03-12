import os
import shutil

from pricewatch.net.http_client import HttpClient


TEST_CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")


def make_test_client(verbose=True, cache_dir=TEST_CACHE_DIR):
    if os.path.exists(cache_dir):
        shutil.rmtree(cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    return HttpClient(
        cache_dir=cache_dir,
        cache_max_age_days=30,
        min_delay=0,
        max_delay=0,
        fast_mode=True,
        timeout=15,
        verbose=verbose,
    )

