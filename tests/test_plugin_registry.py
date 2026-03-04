import os
import sys
import importlib
import pytest

root_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, root_dir)

from pricewatch.core.plugin_loader import discover_adapters, ShopRegistry, ReferenceAdapterNotFound
from pricewatch.core.registry import get_registry
from pricewatch.core.normalize import MAIN_NORMALIZED, normalize_title, product_exists_on_main


def test_discover_plugins():
    adapters = discover_adapters("pricewatch.shops")
    names = sorted(a.name for a in adapters)
    assert names == sorted(["prohockey", "hockeyshans", "hockeyshop", "hockeyworld"])


def test_registry_for_url():
    registry = get_registry()
    assert registry.for_url("https://prohockey.com.ua") is not None
    assert registry.for_url("https://prohockey.com.ua").name == "prohockey"
    assert registry.for_url("https://hockeyshans.com.ua/category/2").name == "hockeyshans"
    assert registry.for_url("https://hockeyshop.com.ua").name == "hockeyshop"
    assert registry.for_url("https://hockeyworld.com.ua").name == "hockeyworld"


def test_product_exists_on_main():
    MAIN_NORMALIZED.clear()
    MAIN_NORMALIZED.append(normalize_title("Bauer Vapor Stick"))
    assert product_exists_on_main("Bauer Vapor Stick") is True
    assert product_exists_on_main("Bauer Vapor Stick 2024") is True


def test_reference_adapter_missing():
    dummy_adapters = discover_adapters("tests.dummy_shops")
    registry = ShopRegistry(dummy_adapters)
    with pytest.raises(ReferenceAdapterNotFound):
        registry.reference_adapter()


def test_discover_dummy_adapters():
    adapters = discover_adapters("tests.dummy_shops")
    names = sorted(a.name for a in adapters)
    assert names == sorted(["dummy_one", "dummy_two"])


def test_facade_imports():
    importlib.import_module("parser")
    # legacy module removed from project; previously we ensured backward compatibility
    # by importing it here. No-op now.
