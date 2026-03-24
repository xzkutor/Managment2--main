from __future__ import annotations

from decimal import Decimal
from typing import Union

from sqlalchemy.orm import Session, joinedload

from pricewatch.db.models import Product, ProductMapping, ProductPriceHistory, utcnow
from pricewatch.db.services.normalization import normalize_product_name

# Price values accepted by this module.  The ORM model uses Numeric(12,4)
# which maps to Decimal on read.  Both float and Decimal are accepted on
# write to remain backward-compatible with callers that still pass floats.
_PriceType = Union[Decimal, float, None]


def get_product_by_url(session: Session, store_id: int, product_url: str) -> Product | None:
    return (
        session.query(Product)
        .filter(Product.store_id == store_id, Product.product_url == product_url)
        .one_or_none()
    )


def list_products_by_store(session: Session, store_id: int) -> list[Product]:
    return session.query(Product).filter(Product.store_id == store_id).order_by(Product.id).all()


def list_products_by_category(session: Session, category_id: int) -> list[Product]:
    return session.query(Product).filter(Product.category_id == category_id).order_by(Product.id).all()


def search_products_by_categories(
    session: Session,
    *,
    target_category_ids: list[int],
    reference_product_id: int,
    search: str | None = None,
    limit: int = 50,
    include_rejected: bool = False,
) -> list[Product]:
    """Return eligible target products scoped to the given category IDs.

    All filtering is performed at the DB level to avoid loading large
    in-memory result sets:

    1. ``Product.category_id IN target_category_ids``
    2. Optional case-insensitive name search (SQL ILIKE / LOWER LIKE).
    3. Exclude targets that are already ``confirmed`` in any ProductMapping
       (globally confirmed — for any reference product).
    4. When ``include_rejected=False`` (default), exclude targets that have
       a ``rejected`` ProductMapping row for *this* ``reference_product_id``.
    5. Deterministic ordering by ``Product.id``.
    6. Hard ``limit`` applied at the DB layer.
    7. Category relationship is eagerly loaded to avoid N+1 on serialization.

    Parameters
    ----------
    target_category_ids:
        Allowlist of target category IDs to search within.
    reference_product_id:
        The reference-side product the operator is resolving.
    search:
        Optional substring filter (case-insensitive).
    limit:
        Maximum number of rows to return.
    include_rejected:
        When ``True``, skip the rejected-pair exclusion filter so that
        previously rejected targets are surfaced again.
    """
    if not target_category_ids:
        return []

    # Subquery: globally confirmed targets (any reference product)
    confirmed_subq = (
        session.query(ProductMapping.target_product_id)
        .filter(ProductMapping.match_status == "confirmed")
        .scalar_subquery()
    )

    q = (
        session.query(Product)
        .options(joinedload(Product.category))
        .filter(Product.category_id.in_(target_category_ids))
        .filter(~Product.id.in_(confirmed_subq))
    )

    # Case-insensitive name search pushed to DB
    if search:
        q = q.filter(Product.name.ilike(f"%{search}%"))

    # Exclude rejected pairs for this specific reference product
    if not include_rejected:
        rejected_subq = (
            session.query(ProductMapping.target_product_id)
            .filter(
                ProductMapping.reference_product_id == reference_product_id,
                ProductMapping.match_status == "rejected",
            )
            .scalar_subquery()
        )
        q = q.filter(~Product.id.in_(rejected_subq))

    return q.order_by(Product.id).limit(limit).all()


def find_products_by_name_hash(session: Session, name_hash: str) -> list[Product]:
    return session.query(Product).filter(Product.name_hash == name_hash).all()


def add_price_history(
    session: Session,
    *,
    product_id: int,
    price: _PriceType,
    currency: str | None,
    source_url: str | None,
    scrape_run_id: int | None,
) -> ProductPriceHistory:
    history = ProductPriceHistory(
        product_id=product_id,
        price=price,
        currency=currency,
        source_url=source_url,
        scrape_run_id=scrape_run_id,
    )
    session.add(history)
    session.flush()
    return history


def _price_changed(old: _PriceType, new: _PriceType) -> bool:
    """Return True if the price value has materially changed.

    Compares using Decimal-safe equality to avoid floating-point noise.
    """
    if old is None and new is None:
        return False
    if (old is None) != (new is None):
        return True
    # Normalize to Decimal for exact comparison
    try:
        return Decimal(str(old)) != Decimal(str(new))
    except Exception:
        return old != new


def upsert_product(
    session: Session,
    *,
    store_id: int,
    product_url: str,
    name: str,
    price: _PriceType = None,
    currency: str | None = None,
    category_id: int | None = None,
    external_id: str | None = None,
    description: str | None = None,
    source_url: str | None = None,
    is_available: bool | None = None,
    scrape_run_id: int | None = None,
    with_status: bool = False,
) -> Product | tuple[Product, bool, bool]:
    """Create or update a product summary. `product_url` is required for uniqueness."""
    if not product_url or not str(product_url).strip():
        raise ValueError("product_url is required")
    product_url = str(product_url).strip()

    normalized_name, name_hash = normalize_product_name(name)
    now = utcnow()

    product = get_product_by_url(session, store_id, product_url)
    if product:
        price_changed = _price_changed(product.price, price)
        product.name = name
        product.normalized_name = normalized_name
        product.name_hash = name_hash
        product.price = price
        product.currency = currency
        product.category_id = category_id
        product.external_id = external_id
        product.description = description
        product.source_url = source_url
        product.is_available = is_available if is_available is not None else product.is_available
        product.scrape_run_id = scrape_run_id
        product.scraped_at = now
        product.updated_at = now
        if price_changed:
            add_price_history(
                session,
                product_id=product.id,
                price=price,
                currency=currency,
                source_url=source_url or product.product_url,
                scrape_run_id=scrape_run_id,
            )
        session.flush()
        return (product, False, price_changed) if with_status else product

    product = Product(
        store_id=store_id,
        product_url=product_url,
        name=name,
        normalized_name=normalized_name,
        name_hash=name_hash,
        price=price,
        currency=currency,
        category_id=category_id,
        external_id=external_id,
        description=description,
        source_url=source_url,
        is_available=is_available if is_available is not None else True,
        scrape_run_id=scrape_run_id,
        scraped_at=now,
    )
    session.add(product)
    session.flush()

    price_changed = False
    if price is not None:
        add_price_history(
            session,
            product_id=product.id,
            price=price,
            currency=currency,
            source_url=source_url or product.product_url,
            scrape_run_id=scrape_run_id,
        )
        price_changed = True

    return (product, True, price_changed) if with_status else product
