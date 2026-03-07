from __future__ import annotations

from typing import cast
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import exists
from sqlalchemy import func

from pricewatch.db.models import Category, CategoryMapping, Product
from pricewatch.db.services.normalization import normalize_category_name
from pricewatch.db.models import utcnow


def get_category_by_name(session: Session, store_id: int, name: str) -> Category | None:
    return (
        session.query(Category)
        .filter(Category.store_id == store_id, Category.name == name)
        .one_or_none()
    )


def list_categories_by_store(session: Session, store_id: int) -> list[Category]:
    return cast(list[Category], cast(object, (
        session.query(Category)
        .filter(Category.store_id == store_id)
        .order_by(Category.name)
        .all()
    )))


def list_unmapped_categories(session: Session, store_id: int, *, as_reference: bool = True) -> list[Category]:
    q = session.query(Category).filter(Category.store_id == store_id)
    mapping_column = CategoryMapping.reference_category_id if as_reference else CategoryMapping.target_category_id
    mapping_exists = exists().where(mapping_column == Category.id)
    q = q.filter(~mapping_exists)
    return cast(list[Category], cast(object, q.order_by(Category.name).all()))


def get_category(session: Session, category_id: int) -> Category | None:
    return session.get(Category, category_id)


def upsert_category(
    session: Session,
    *,
    store_id: int,
    name: str,
    external_id: str | None = None,
    url: str | None = None,
) -> Category:
    category = get_category_by_name(session, store_id, name)
    normalized_name = normalize_category_name(name)
    if category:
        category.external_id = external_id
        category.url = url
        category.normalized_name = normalized_name
        category.updated_at = utcnow()
        session.flush()
        return category

    category = Category(
        store_id=store_id,
        name=name,
        normalized_name=normalized_name,
        external_id=external_id,
        url=url,
    )
    session.add(category)
    session.flush()
    return category


def create_category_mapping(
    session: Session,
    *,
    reference_category_id: int,
    target_category_id: int,
    match_type: str | None = None,
    confidence: float | None = None,
) -> CategoryMapping:
    existing = get_category_mapping(
        session,
        reference_category_id=reference_category_id,
        target_category_id=target_category_id,
    )
    if existing:
        updated = False
        if existing.match_type != match_type:
            existing.match_type = match_type
            updated = True
        if existing.confidence != confidence:
            existing.confidence = confidence
            updated = True
        if updated:
            existing.updated_at = utcnow()
            session.flush()
        assert isinstance(existing, CategoryMapping)
        return existing

    mapping: CategoryMapping = CategoryMapping(
        reference_category_id=reference_category_id,
        target_category_id=target_category_id,
        match_type=match_type,
        confidence=confidence,
    )
    session.add(mapping)
    session.flush()
    return mapping


def get_category_mapping(
    session: Session,
    *,
    reference_category_id: int,
    target_category_id: int,
) -> CategoryMapping | None:
    return (
        session.query(CategoryMapping)
        .filter(
            CategoryMapping.reference_category_id == reference_category_id,
            CategoryMapping.target_category_id == target_category_id,
        )
        .one_or_none()
    )


def update_category_mapping(
    session: Session,
    mapping_id: int,
    *,
    match_type: str | None = None,
    confidence: float | None = None,
) -> CategoryMapping:
    mapping = session.get(CategoryMapping, mapping_id)
    if not mapping:
        raise ValueError(f"CategoryMapping {mapping_id} not found")
    if match_type is not None:
        mapping.match_type = match_type
    if confidence is not None:
        mapping.confidence = confidence
    mapping.updated_at = utcnow()
    session.flush()
    assert isinstance(mapping, CategoryMapping)
    return mapping


def delete_category_mapping(session: Session, mapping_id: int) -> None:
    mapping = session.get(CategoryMapping, mapping_id)
    if mapping:
        session.delete(mapping)
        session.flush()


def list_category_mappings(session: Session, *, reference_store_id: int | None = None, target_store_id: int | None = None) -> list[CategoryMapping]:
    q = session.query(CategoryMapping).options(
        joinedload(CategoryMapping.reference_category).joinedload(Category.store),
        joinedload(CategoryMapping.target_category).joinedload(Category.store),
    )
    if reference_store_id is not None:
        q = q.filter(CategoryMapping.reference_category.has(store_id=reference_store_id))
    if target_store_id is not None:
        q = q.filter(CategoryMapping.target_category.has(store_id=target_store_id))
    return cast(list[CategoryMapping], cast(object, q.all()))


def count_products_by_category(session: Session, store_id: int) -> dict[int, int]:
    """Return a mapping category_id -> product_count for categories in the given store.

    Uses a single aggregated query for efficiency.
    """
    q = (
        session.query(Category.id, func.count(Product.id))
        .outerjoin(Product, Product.category_id == Category.id)
        .filter(Category.store_id == store_id)
        .group_by(Category.id)
    )
    return {cid: count for cid, count in q.all()}

__all__ = [
    "get_category_by_name",
    "list_categories_by_store",
    "list_unmapped_categories",
    "get_category",
    "upsert_category",
    "create_category_mapping",
    "get_category_mapping",
    "update_category_mapping",
    "delete_category_mapping",
    "list_category_mappings",
    "count_products_by_category",
]
