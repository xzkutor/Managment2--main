from __future__ import annotations

from typing import cast
from sqlalchemy.orm import Session

from pricewatch.db.models import ProductMapping, utcnow


def create_product_mapping(
    session: Session,
    *,
    reference_product_id: int,
    target_product_id: int,
    match_status: str | None = None,
    confidence: float | None = None,
    comment: str | None = None,
) -> ProductMapping:
    existing = get_product_mapping(
        session,
        reference_product_id=reference_product_id,
        target_product_id=target_product_id,
    )
    if existing:
        updated = False
        if existing.match_status != match_status:
            existing.match_status = match_status
            updated = True
        if existing.confidence != confidence:
            existing.confidence = confidence
            updated = True
        if existing.comment != comment:
            existing.comment = comment
            updated = True
        if updated:
            existing.updated_at = utcnow()
            session.flush()
        return existing

    mapping = ProductMapping(
        reference_product_id=reference_product_id,
        target_product_id=target_product_id,
        match_status=match_status,
        confidence=confidence,
        comment=comment,
    )
    session.add(mapping)
    session.flush()
    return mapping


def get_product_mapping(
    session: Session,
    *,
    reference_product_id: int,
    target_product_id: int,
) -> ProductMapping | None:
    return (
        session.query(ProductMapping)
        .filter(
            ProductMapping.reference_product_id == reference_product_id,
            ProductMapping.target_product_id == target_product_id,
        )
        .one_or_none()
    )


def list_matches_for_reference_product(session: Session, reference_product_id: int) -> list[ProductMapping]:
    return cast(list[ProductMapping], cast(object, (
        session.query(ProductMapping)
        .filter(ProductMapping.reference_product_id == reference_product_id)
        .all()
    )))


def list_matches_for_target_product(session: Session, target_product_id: int) -> list[ProductMapping]:
    return cast(list[ProductMapping], cast(object, (
        session.query(ProductMapping)
        .filter(ProductMapping.target_product_id == target_product_id)
        .all()
    )))


def update_product_mapping(
    session: Session,
    mapping_id: int,
    *,
    match_status: str | None = None,
    confidence: float | None = None,
    comment: str | None = None,
) -> ProductMapping:
    mapping = session.get(ProductMapping, mapping_id)
    if not mapping:
        raise ValueError(f"ProductMapping {mapping_id} not found")
    if match_status is not None:
        mapping.match_status = match_status
    if confidence is not None:
        mapping.confidence = confidence
    if comment is not None:
        mapping.comment = comment
    mapping.updated_at = utcnow()
    session.flush()
    assert isinstance(mapping, ProductMapping)
    return mapping


def delete_product_mapping(session: Session, mapping_id: int) -> None:
    mapping = session.get(ProductMapping, mapping_id)
    if mapping:
        session.delete(mapping)
        session.flush()


def list_product_mappings(session: Session, *, reference_store_id: int | None = None, target_store_id: int | None = None) -> list[ProductMapping]:
    q = session.query(ProductMapping)
    if reference_store_id is not None:
        q = q.join(ProductMapping.reference_product)
        q = q.filter(ProductMapping.reference_product.has(store_id=reference_store_id))
    if target_store_id is not None:
        q = q.join(ProductMapping.target_product)
        q = q.filter(ProductMapping.target_product.has(store_id=target_store_id))
    return cast(list[ProductMapping], cast(object, q.all()))
