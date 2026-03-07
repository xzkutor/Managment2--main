from __future__ import annotations

from pricewatch.db.repositories import (
    create_category_mapping,
    update_category_mapping,
    delete_category_mapping,
    list_category_mappings,
)
from pricewatch.db.models import Category


class MappingService:
    def __init__(self, session):
        self.session = session

    def list_category_mappings(self, *, reference_store_id: int | None = None, target_store_id: int | None = None):
        return list_category_mappings(self.session, reference_store_id=reference_store_id, target_store_id=target_store_id)

    def create_category_mapping(self, *, reference_category_id: int, target_category_id: int, match_type: str | None = None, confidence: float | None = None):
        # validate categories and stores
        ref_cat = self.session.get(Category, reference_category_id) if hasattr(self.session, 'get') else None
        tgt_cat = self.session.get(Category, target_category_id) if hasattr(self.session, 'get') else None
        if not ref_cat:
            raise ValueError(f"Reference category {reference_category_id} not found")
        if not tgt_cat:
            raise ValueError(f"Target category {target_category_id} not found")

        ref_store = getattr(ref_cat, 'store', None)
        tgt_store = getattr(tgt_cat, 'store', None)

        # reference_category must belong to a reference store
        if not getattr(ref_store, 'is_reference', False):
            raise ValueError("reference_category_id must belong to a reference store")
        # target_category must NOT belong to a reference store
        if getattr(tgt_store, 'is_reference', False):
            raise ValueError("target_category_id must not belong to a reference (reference store)")
        # categories must not be from the same store
        if getattr(ref_cat, 'store_id', None) is not None and getattr(tgt_cat, 'store_id', None) is not None:
            if ref_cat.store_id == tgt_cat.store_id:
                raise ValueError("reference and target categories must not belong to the same store")

        return create_category_mapping(
            self.session,
            reference_category_id=reference_category_id,
            target_category_id=target_category_id,
            match_type=match_type,
            confidence=confidence,
        )

    def update_category_mapping(self, mapping_id: int, *, match_type: str | None = None, confidence: float | None = None):
        # Only metadata fields are editable; backend enforces immutability of the pair.
        return update_category_mapping(
            self.session,
            mapping_id,
            match_type=match_type,
            confidence=confidence,
        )

    def delete_category_mapping(self, mapping_id: int):
        delete_category_mapping(self.session, mapping_id)
        return {"deleted": True, "mapping_id": mapping_id}
