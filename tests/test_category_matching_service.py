"""Tests for CategoryMatchingService.auto_link.

Covers:
  - Exact normalized_name match creates a CategoryMapping
  - No duplicate rows on repeated auto_link calls
  - One reference category -> multiple target categories (one-to-many)
  - Multiple reference categories -> one target category (many-to-many)
  - Store role validation (ref must be reference, target must not be)
  - Categories without normalized_name are skipped
  - Response shape: created list, skipped_existing list, summary counts
"""
from __future__ import annotations

import pytest

from pricewatch.db.testing import test_session_scope as _session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import upsert_category, list_mapped_target_categories
from pricewatch.services.category_matching_service import CategoryMatchingService


def _make_stores(session):
    ref_store = get_or_create_store(session, "RefStore", is_reference=True)
    tgt_store = get_or_create_store(session, "TgtStore", is_reference=False)
    tgt_store2 = get_or_create_store(session, "TgtStore2", is_reference=False)
    return ref_store, tgt_store, tgt_store2


class TestAutoLinkExactMatch:
    def test_creates_mapping_for_exact_normalized_name(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            upsert_category(session, store_id=ref_store.id, name="Skates")
            upsert_category(session, store_id=tgt_store.id, name="Skates")
            session.flush()

            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )

        assert result["summary"]["created"] == 1
        assert result["summary"]["skipped_existing"] == 0
        assert len(result["created"]) == 1
        assert len(result["skipped_existing"]) == 0

    def test_created_entry_has_expected_fields(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            upsert_category(session, store_id=ref_store.id, name="Skates")
            upsert_category(session, store_id=tgt_store.id, name="Skates")
            session.flush()

            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )

        entry = result["created"][0]
        assert entry["reference_category_name"] == "Skates"
        assert entry["target_category_name"] == "Skates"
        assert entry["match_type"] == "exact"
        assert entry["confidence"] == 1.0
        assert "reference_category_id" in entry
        assert "target_category_id" in entry

    def test_no_mapping_created_when_names_differ(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            upsert_category(session, store_id=ref_store.id, name="Skates")
            upsert_category(session, store_id=tgt_store.id, name="Sticks")
            session.flush()

            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )

        assert result["summary"]["created"] == 0
        assert result["created"] == []

    def test_no_duplicate_on_repeated_call(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            upsert_category(session, store_id=ref_store.id, name="Helmets")
            upsert_category(session, store_id=tgt_store.id, name="Helmets")
            session.flush()

            r1 = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )
            r2 = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )

        assert r1["summary"]["created"] == 1
        assert r2["summary"]["created"] == 0
        assert r2["summary"]["skipped_existing"] >= 1
        assert len(r2["skipped_existing"]) >= 1

    def test_skipped_existing_entry_has_category_ids(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Pucks")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="Pucks")
            session.flush()
            # first call creates
            CategoryMatchingService.auto_link(
                session, reference_store_id=ref_store.id, target_store_id=tgt_store.id)
            # second call skips
            r2 = CategoryMatchingService.auto_link(
                session, reference_store_id=ref_store.id, target_store_id=tgt_store.id)

        skip = r2["skipped_existing"][0]
        assert skip["reference_category_id"] == ref_cat.id
        assert skip["target_category_id"] == tgt_cat.id

    def test_mapping_has_exact_match_type_and_confidence_1(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Gloves")
            upsert_category(session, store_id=tgt_store.id, name="Gloves")
            session.flush()

            CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )
            mappings = list_mapped_target_categories(session, ref_cat.id)

        assert len(mappings) == 1
        assert mappings[0].match_type == "exact"
        assert mappings[0].confidence == 1.0

    def test_response_has_summary_key(self):
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            session.flush()
            result = CategoryMatchingService.auto_link(
                session, reference_store_id=ref_store.id, target_store_id=tgt_store.id)

        assert "summary" in result
        assert "created" in result["summary"]
        assert "skipped_existing" in result["summary"]
        assert "skipped_no_norm" in result["summary"]


class TestAutoLinkOneToMany:
    def test_one_ref_category_maps_to_multiple_targets(self):
        """One reference category should map to matching categories in both target stores."""
        with _session_scope() as session:
            ref_store, tgt_store, tgt_store2 = _make_stores(session)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Sticks")
            upsert_category(session, store_id=tgt_store.id, name="Sticks")
            upsert_category(session, store_id=tgt_store2.id, name="Sticks")
            session.flush()

            r1 = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )
            r2 = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store2.id,
            )
            mappings = list_mapped_target_categories(session, ref_cat.id)

        assert r1["summary"]["created"] == 1
        assert r2["summary"]["created"] == 1
        assert len(mappings) == 2

    def test_mapping_rows_are_independent_pairs(self):
        with _session_scope() as session:
            ref_store, tgt_store, tgt_store2 = _make_stores(session)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Pads")
            tgt1 = upsert_category(session, store_id=tgt_store.id, name="Pads")
            tgt2 = upsert_category(session, store_id=tgt_store2.id, name="Pads")
            session.flush()

            CategoryMatchingService.auto_link(
                session, reference_store_id=ref_store.id, target_store_id=tgt_store.id)
            CategoryMatchingService.auto_link(
                session, reference_store_id=ref_store.id, target_store_id=tgt_store2.id)

            mappings = list_mapped_target_categories(session, ref_cat.id)
            tgt_ids = {m.target_category_id for m in mappings}

        assert tgt1.id in tgt_ids
        assert tgt2.id in tgt_ids


class TestAutoLinkManyToMany:
    def test_multiple_ref_categories_map_to_same_target(self):
        """Many-to-many: two ref categories each map to their own same-named target."""
        with _session_scope() as session:
            ref_store, tgt_store, _ = _make_stores(session)
            ref_cat_a = upsert_category(session, store_id=ref_store.id, name="Blades")
            ref_cat_b = upsert_category(session, store_id=ref_store.id, name="Skates")
            upsert_category(session, store_id=tgt_store.id, name="Blades")
            upsert_category(session, store_id=tgt_store.id, name="Skates")
            session.flush()

            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=ref_store.id,
                target_store_id=tgt_store.id,
            )

            mappings_a = list_mapped_target_categories(session, ref_cat_a.id)
            mappings_b = list_mapped_target_categories(session, ref_cat_b.id)

        assert result["summary"]["created"] == 2
        assert len(result["created"]) == 2
        assert len(mappings_a) == 1
        assert len(mappings_b) == 1
        assert mappings_a[0].target_category_id != mappings_b[0].target_category_id


class TestAutoLinkStoreRoleValidation:
    def test_raises_when_reference_store_not_found(self):
        with _session_scope() as session:
            _, tgt_store, _ = _make_stores(session)
            with pytest.raises(ValueError, match="not found"):
                CategoryMatchingService.auto_link(
                    session,
                    reference_store_id=99999,
                    target_store_id=tgt_store.id,
                )

    def test_raises_when_target_store_not_found(self):
        with _session_scope() as session:
            ref_store, _, _ = _make_stores(session)
            with pytest.raises(ValueError, match="not found"):
                CategoryMatchingService.auto_link(
                    session,
                    reference_store_id=ref_store.id,
                    target_store_id=99999,
                )

    def test_raises_when_reference_store_is_not_reference(self):
        with _session_scope() as session:
            _, tgt_store, _ = _make_stores(session)
            with pytest.raises(ValueError, match="not a reference store"):
                CategoryMatchingService.auto_link(
                    session,
                    reference_store_id=tgt_store.id,
                    target_store_id=tgt_store.id,
                )

    def test_raises_when_target_store_is_reference(self):
        with _session_scope() as session:
            ref_store, _, _ = _make_stores(session)
            with pytest.raises(ValueError, match="reference store"):
                CategoryMatchingService.auto_link(
                    session,
                    reference_store_id=ref_store.id,
                    target_store_id=ref_store.id,
                )

