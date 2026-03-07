#!/usr/bin/env python
"""Example demonstrating cache usage with safe_get"""

import time
import os
import shutil
import logging
from http_client import make_default_client

logger = logging.getLogger(__name__)


def demo_cache_usage():
    """Demonstrate cache functionality"""
    client = make_default_client()

    # Clean up cache from previous runs
    if os.path.exists(client.cache_dir):
        shutil.rmtree(client.cache_dir)

    # Test URL (using httpbin for testing)
    test_url = "https://httpbin.org/html"

    logger.info("%s", "=" * 60)
    logger.info("Cache Demo: Fetching the same URL twice")
    logger.info("%s", "=" * 60)

    # First request - should hit the network
    logger.info("\n1. First request to %s", test_url)
    logger.info("   (should fetch from network and cache)")
    start = time.time()
    response1 = client.safe_get(test_url, use_cache=True)
    elapsed1 = time.time() - start

    if response1:
        logger.info("   Status: %s", response1.status_code)
        logger.info("   Size: %s bytes", len(response1.content))
        logger.info("   Time: %.3fs (includes network delay)", elapsed1)

    # Small delay to ensure times are different
    time.sleep(1)

    # Second request - should load from cache
    logger.info("\n2. Second request to %s", test_url)
    logger.info("   (should load from cache)")
    start = time.time()
    response2 = client.safe_get(test_url, use_cache=True)
    elapsed2 = time.time() - start

    if response2:
        logger.info("   Status: %s", response2.status_code)
        logger.info("   Size: %s bytes", len(response2.content))
        logger.info("   Time: %.3fs (from cache, much faster)", elapsed2)

    # Verify cache contents match
    if response1 and response2:
        if response1.content == response2.content:
            logger.info("\n✓ Content matches between network and cache")
        else:
            logger.warning("\n✗ Content mismatch!")

    # Show speedup
    if elapsed1 > 0:
        speedup = elapsed1 / elapsed2 if elapsed2 > 0 else float('inf')
        logger.info("\n✓ Speedup: %.1fx faster from cache", speedup)

    # Third request with caching disabled
    logger.info("\n3. Third request to %s", test_url)
    logger.info("   (caching disabled - should fetch from network again)")
    start = time.time()
    response3 = client.safe_get(test_url, use_cache=False)
    elapsed3 = time.time() - start

    if response3:
        logger.info("   Status: %s", response3.status_code)
        logger.info("   Time: %.3fs (network request)", elapsed3)

    logger.info("\n%s", "=" * 60)
    logger.info("Cache directory: %s", os.path.abspath(client.cache_dir))
    if os.path.exists(client.cache_dir):
        files = os.listdir(client.cache_dir)
        logger.info("Cached files: %s", len(files))
        for f in files:
            size = os.path.getsize(os.path.join(client.cache_dir, f))
            logger.info("  - %s (%s bytes)", f, size)
    logger.info("%s", "=" * 60)

    # Cleanup
    if os.path.exists(client.cache_dir):
        shutil.rmtree(client.cache_dir)
        logger.info("\nCleaned up cache directory")


if __name__ == '__main__':
    try:
        demo_cache_usage()
    except Exception as e:
        logger.exception("Error in demo cache usage: %s", e)
        logger.info("\nNote: This demo requires internet connection.")
        logger.info("Running with httpbin.org for testing purposes.")
