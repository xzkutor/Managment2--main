from __future__ import annotations

from sqlalchemy.orm import Session

from pricewatch.db.models import Product, ProductPriceHistory, utcnow
from pricewatch.db.services.normalization import normalize_product_name


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


def find_products_by_name_hash(session: Session, name_hash: str) -> list[Product]:
    return session.query(Product).filter(Product.name_hash == name_hash).all()


def add_price_history(
    session: Session,
    *,
    product_id: int,
    price: float | None,
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


def _price_changed(old: float | None, new: float | None) -> bool:
    return (old is None) != (new is None) or (old is not None and new is not None and old != new)


def upsert_product(
    session: Session,
    *,
    store_id: int,
    product_url: str,
    name: str,
    price: float | None = None,
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
