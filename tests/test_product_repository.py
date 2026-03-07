import pytest

from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.testing import test_session_scope as session_scope


def test_upsert_product_requires_product_url():
    with session_scope() as session:
        with pytest.raises(ValueError):
            upsert_product(
                session,
                store_id=1,
                product_url="   ",
                name="Test Product",
            )
import pytest

from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.testing import test_session_scope as session_scope


def test_upsert_product_requires_product_url():
    with session_scope() as session:
        with pytest.raises(ValueError):
            upsert_product(
                session,
                store_id=1,
                product_url="   ",
                name="Test Product",
            )
