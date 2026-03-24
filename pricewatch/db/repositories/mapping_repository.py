from __future__ import annotations
from typing import cast
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload
from pricewatch.db.models import ProductMapping, Product, Category, utcnow
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
def upsert_match_decision(
    session: Session,
    *,
    reference_product_id: int,
    target_product_id: int,
    match_status: str,
    confidence: float | None = None,
    comment: str | None = None,
) -> ProductMapping:
    """Create or update an explicit match decision for the given pair.
    This is the canonical write path for both ``confirmed`` and ``rejected``
    decisions.  The latest call for the same pair always wins — status
    transitions (e.g. ``rejected -> confirmed``) are allowed.
    """
    return create_product_mapping(
        session,
        reference_product_id=reference_product_id,
        target_product_id=target_product_id,
        match_status=match_status,
        confidence=confidence,
        comment=comment,
    )
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
def list_product_mappings(
    session: Session,
    *,
    reference_store_id: int | None = None,
    target_store_id: int | None = None,
) -> list[ProductMapping]:
    q = session.query(ProductMapping)
    if reference_store_id is not None:
        q = q.join(ProductMapping.reference_product)
        q = q.filter(ProductMapping.reference_product.has(store_id=reference_store_id))
    if target_store_id is not None:
        q = q.join(ProductMapping.target_product)
        q = q.filter(ProductMapping.target_product.has(store_id=target_store_id))
    return cast(list[ProductMapping], cast(object, q.all()))
def list_product_mappings_filtered(
    session: Session,
    *,
    reference_store_id: int | None = None,
    target_store_id: int | None = None,
    reference_category_id: int | None = None,
    target_category_id: int | None = None,
    status: str | None = "confirmed",
    search: str | None = None,
    limit: int | None = 500,
) -> list[ProductMapping]:
    """Return ProductMapping rows with optional rich filters.
    Eagerly loads reference_product and target_product (and their categories /
    stores) so that serializers can access them without extra queries.
    Parameters
    ----------
    status:
        Defaults to ``"confirmed"``.  Pass ``None`` to return all statuses.
    search:
        Case-insensitive substring match applied to both reference and target
        product names.
    limit:
        Maximum number of rows returned.  Defaults to 500 to prevent
        accidental full-table reads.
    """
    q = (
        session.query(ProductMapping)
        .options(
            joinedload(ProductMapping.reference_product).joinedload(Product.category).joinedload(Category.store),
            joinedload(ProductMapping.target_product).joinedload(Product.category).joinedload(Category.store),
        )
    )
    if status is not None:
        q = q.filter(ProductMapping.match_status == status)
    if reference_store_id is not None:
        q = q.filter(
            ProductMapping.reference_product_id.in_(
                session.query(Product.id).filter(Product.store_id == reference_store_id)
            )
        )
    if target_store_id is not None:
        q = q.filter(
            ProductMapping.target_product_id.in_(
                session.query(Product.id).filter(Product.store_id == target_store_id)
            )
        )
    if reference_category_id is not None:
        q = q.filter(
            ProductMapping.reference_product_id.in_(
                session.query(Product.id).filter(Product.category_id == reference_category_id)
            )
        )
    if target_category_id is not None:
        q = q.filter(
            ProductMapping.target_product_id.in_(
                session.query(Product.id).filter(Product.category_id == target_category_id)
            )
        )
    if search:
        needle = f"%{search}%"
        q = q.filter(
            or_(
                ProductMapping.reference_product.has(Product.name.ilike(needle)),
                ProductMapping.target_product.has(Product.name.ilike(needle)),
            )
        )
    if limit:
        q = q.limit(limit)
    return cast(list[ProductMapping], cast(object, q.all()))
def get_confirmed_target_ids_for_refs(
    session: Session,
    reference_product_ids: list[int],
) -> dict[int, set[int]]:
    """Return a mapping of {reference_product_id: {confirmed_target_product_ids}}.
    Only ``confirmed`` rows are included.  Useful for batch pre-loading
    in comparison logic to avoid N+1 queries.
    """
    if not reference_product_ids:
        return {}
    rows = (
        session.query(ProductMapping)
        .filter(
            ProductMapping.reference_product_id.in_(reference_product_ids),
            ProductMapping.match_status == "confirmed",
        )
        .all()
    )
    result: dict[int, set[int]] = {}
    for pm in rows:
        ref_id = int(pm.reference_product_id)
        tgt_id = int(pm.target_product_id)
        result.setdefault(ref_id, set()).add(tgt_id)
    return result
def get_rejected_pairs_for_refs(
    session: Session,
    reference_product_ids: list[int],
) -> set[tuple[int, int]]:
    """Return a set of ``(reference_product_id, target_product_id)`` pairs
    that are explicitly marked ``rejected`` for the given reference products.
    Used by ComparisonService to suppress rejected pairs from future results.
    """
    if not reference_product_ids:
        return set()
    rows = (
        session.query(ProductMapping)
        .filter(
            ProductMapping.reference_product_id.in_(reference_product_ids),
            ProductMapping.match_status == "rejected",
        )
        .all()
    )
    return {(int(pm.reference_product_id), int(pm.target_product_id)) for pm in rows}
def get_all_confirmed_target_ids(
    session: Session,
    target_product_ids: list[int],
) -> set[int]:
    """Return the subset of ``target_product_ids`` that have a ``confirmed``
    ProductMapping (for any reference product).
    Used by eligible-target lookup to block already-confirmed targets.
    """
    if not target_product_ids:
        return set()
    rows = (
        session.query(ProductMapping.target_product_id)
        .filter(
            ProductMapping.target_product_id.in_(target_product_ids),
            ProductMapping.match_status == "confirmed",
        )
        .all()
    )
    return {int(r[0]) for r in rows}
