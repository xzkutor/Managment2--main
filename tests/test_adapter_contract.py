import inspect

from pricewatch.shops.hockeyshans.adapter import HockeyShansAdapter
from pricewatch.shops.hockeyshop.adapter import HockeyShopAdapter
from pricewatch.shops.hockeyworld.adapter import HockeyWorldAdapter
from pricewatch.shops.prohockey.adapter import ProHockeyAdapter


def test_get_products_by_category_signature_consistent():
    """Every adapter must expose category first, client second (optional)"""
    adapters = [HockeyWorldAdapter, HockeyShopAdapter, HockeyShansAdapter, ProHockeyAdapter]
    for adapter_cls in adapters:
        sig = inspect.signature(adapter_cls.get_products_by_category)
        params = list(sig.parameters.values())
        assert len(params) == 3, f"{adapter_cls.__name__} expected 3 params (self, category, client)"
        assert params[1].name == "category", f"{adapter_cls.__name__}: category must come before client"
        assert params[2].name == "client", f"{adapter_cls.__name__}: client must be second parameter"
        assert params[2].default is None, f"{adapter_cls.__name__}: client should default to None"
