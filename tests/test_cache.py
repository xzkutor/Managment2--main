#!/usr/bin/env python
"""Test caching functionality for HttpClient.safe_get"""

import os
import sys
import time
from unittest.mock import Mock

root_dir = os.path.dirname(os.path.dirname(__file__))
tests_dir = os.path.dirname(__file__)
sys.path.insert(0, root_dir)
sys.path.insert(0, tests_dir)

from test_utils import make_test_client


def test_cache_path_generation():
    """Test that cache path is generated correctly"""
    client = make_test_client(verbose=False)
    url = "https://example.com/page"
    cache_path = client._get_cache_path(url)
    assert cache_path.startswith(client.cache_dir)
    assert cache_path.endswith('.cache')
    print(f"✓ Cache path generation: {cache_path}")


def test_cache_save_load():
    """Test saving and loading cache"""
    client = make_test_client(verbose=False)
    cache_path = client._get_cache_path("https://example.com/test")
    test_content = b"Test content for cache"

    # Save to cache
    client._save_to_cache(cache_path, test_content)
    assert os.path.exists(cache_path)
    print(f"✓ Cache saved successfully")

    # Load from cache
    loaded = client._load_from_cache(cache_path)
    assert loaded == test_content
    print(f"✓ Cache loaded successfully")


def test_cache_validity():
    """Test cache expiration logic — uses second-based TTL."""
    ttl_seconds = 600  # 10 minutes
    client = make_test_client(verbose=False, cache_ttl_seconds=ttl_seconds)
    cache_path = client._get_cache_path("https://example.com/validity-test")
    test_content = b"Test content"

    # Create a valid (fresh) cache
    client._save_to_cache(cache_path, test_content)
    assert client._is_cache_valid(cache_path)
    print(f"✓ Fresh cache is valid")

    # Simulate an expired cache by backdating mtime beyond the TTL
    old_time = time.time() - (ttl_seconds + 10)
    os.utime(cache_path, (old_time, old_time))
    assert not client._is_cache_valid(cache_path)
    print(f"✓ Cache older than {ttl_seconds}s TTL is invalid")


def test_safe_get_with_cache():
    """Test safe_get with caching enabled"""
    client = make_test_client(verbose=False)

    # Mock session and response
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html>Cached content</html>"
    mock_response.text = "<html>Cached content</html>"
    mock_response.url = "https://example.com/page"
    mock_response.headers = {'Content-Type': 'text/html'}

    mock_session.request.return_value = mock_response
    mock_session.headers = {}

    # First request should hit the network and cache the response
    result1 = client.safe_get("https://example.com/page", use_cache=True, session=mock_session)

    assert result1 is not None
    assert result1.status_code == 200
    assert mock_session.request.call_count == 1
    print(f"✓ First request hit network and cached response")

    # Second request should load from cache
    result2 = client.safe_get("https://example.com/page", use_cache=True, session=mock_session)

    assert result2 is not None
    assert result2.status_code == 200
    assert mock_session.request.call_count == 1  # Still 1, no new request
    assert result2.content == b"<html>Cached content</html>"
    print(f"✓ Second request loaded from cache")


def test_safe_get_without_cache():
    """Test safe_get with caching disabled"""
    client = make_test_client(verbose=False)
    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.content = b"<html>Content</html>"
    mock_response.text = "<html>Content</html>"
    mock_response.url = "https://example.com/page"
    mock_response.headers = {'Content-Type': 'text/html'}

    mock_session.request.return_value = mock_response
    mock_session.headers = {}

    client.safe_get("https://example.com/test", use_cache=False, session=mock_session)
    client.safe_get("https://example.com/test", use_cache=False, session=mock_session)

    # Both should hit the network
    assert mock_session.request.call_count == 2
    print(f"✓ With use_cache=False, both requests hit network")


def test_only_status_200_cached():
    """Test that only 200 status codes are cached"""
    client = make_test_client(verbose=False)

    mock_session = Mock()
    mock_response = Mock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"
    mock_response.url = "https://example.com/forbidden"
    mock_response.headers = {}

    mock_session.request.return_value = mock_response
    mock_session.headers = {}

    result = client.safe_get("https://example.com/forbidden", use_cache=True, session=mock_session)

    assert result is None
    cache_path = client._get_cache_path("https://example.com/forbidden")
    assert not os.path.exists(cache_path)
    print(f"✓ 403 status code is not cached")


if __name__ == '__main__':
    print("Running cache functionality tests...\n")

    test_cache_path_generation()
    test_cache_save_load()
    test_cache_validity()
    test_safe_get_with_cache()
    test_safe_get_without_cache()
    test_only_status_200_cached()

    print("\n✓ All tests passed!")
