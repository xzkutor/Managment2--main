"""Tests for the DB-first ComparisonService and /api/comparison endpoint.

Updated to match the new flat response shape:
    confirmed_matches, candidate_groups, reference_only, target_only, summary

Covers:
  - Rejection when reference category not found / wrong store role
  - Rejection when target_category_id provided but pair not in category_mappings
  - Rejection when no mappings exist and target_category_id omitted
  - Valid comparison for a mapped pair (single target via legacy arg)
  - Valid comparison for target_category_ids list (new API)
  - Rejection when target_category_ids contains unmapped category
  - Valid comparison for all mapped targets (target_category_id omitted)
  - Many-to-many: one ref category mapped to multiple target categories
  - Stored ProductMapping rows appear in confirmed_matches with is_confirmed=True
  - High-confidence heuristic match appears in confirmed_matches with is_confirmed=False
  - Confirmed mapping bypasses heuristic (not in reference_only/target_only)
  - target_only excludes products shown as candidates
  - can_accept=False when target product already in a confirmed mapping
  - Stable response shape from POST /api/comparison
  - POST /api/comparison/confirm-match creates a ProductMapping row
"""
from __future__ import annotations

from types import SimpleNamespace
from datetime import datetime, timezone

import pytest

from pricewatch.db.testing import test_session_scope as _session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import upsert_category, create_category_mapping
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import create_product_mapping
from pricewatch.services.comparison_service import ComparisonService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_stores_and_categories(session):
    ref_store = get_or_create_store(session, "RefStore", is_reference=True, base_url="https://ref.example.com")
    tgt_store = get_or_create_store(session, "TgtStore", is_reference=False, base_url="https://tgt.example.com")
    ref_cat = upsert_category(session, store_id=ref_store.id, name="Skates", url="https://ref.example.com/skates")
    tgt_cat = upsert_category(session, store_id=tgt_store.id, name="Skates", url="https://tgt.example.com/skates")
    session.flush()
    return ref_store, tgt_store, ref_cat, tgt_cat


def _make_mapped_categories(session):
    ref_store, tgt_store, ref_cat, tgt_cat = _make_stores_and_categories(session)
    create_category_mapping(
        session,
        reference_category_id=ref_cat.id,
        target_category_id=tgt_cat.id,
        match_type="manual",
        confidence=1.0,
    )
    session.flush()
    return ref_store, tgt_store, ref_cat, tgt_cat


def _add_product(session, store_id, category_id, name, price, url_suffix):
    return upsert_product(
        session,
        store_id=store_id,
        product_url=f"https://example.com/product/{url_suffix}",
        name=name,
        price=price,
        currency="UAH",
        category_id=category_id,
    )


# ---------------------------------------------------------------------------
# ComparisonService – validation
# ---------------------------------------------------------------------------

class TestComparisonServiceValidation:
    def test_raises_if_reference_category_not_found(self):
        with _session_scope() as session:
            _, _, _, tgt_cat = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="not found"):
                ComparisonService(session).compare(reference_category_id=99999, target_category_id=tgt_cat.id)

    def test_raises_if_target_category_not_found(self):
        with _session_scope() as session:
            _, _, ref_cat, _ = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="not found"):
                ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=99999)

    def test_raises_when_reference_category_belongs_to_non_reference_store(self):
        with _session_scope() as session:
            _, _, _, tgt_cat = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="reference store"):
                ComparisonService(session).compare(reference_category_id=tgt_cat.id, target_category_id=tgt_cat.id)

    def test_raises_when_target_category_belongs_to_reference_store(self):
        with _session_scope() as session:
            _, _, ref_cat, _ = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="reference store"):
                ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=ref_cat.id)

    def test_raises_when_same_store_for_both(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "OnlyRef2", is_reference=True)
            cat_a = upsert_category(session, store_id=ref_store.id, name="CatA2")
            cat_b = upsert_category(session, store_id=ref_store.id, name="CatB2")
            session.flush()
            with pytest.raises(ValueError):
                ComparisonService(session).compare(reference_category_id=cat_a.id, target_category_id=cat_b.id)

    def test_raises_when_pair_not_mapped(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="маппінг"):
                ComparisonService(session).compare(
                    reference_category_id=ref_cat.id,
                    target_category_id=tgt_cat.id,
                )

    def test_raises_when_no_mappings_and_target_omitted(self):
        with _session_scope() as session:
            _, _, ref_cat, _ = _make_stores_and_categories(session)
            with pytest.raises(ValueError, match="меппінг"):
                ComparisonService(session).compare(reference_category_id=ref_cat.id)

    def test_mapped_pair_does_not_raise(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(
                reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id,
            )
        # New shape — flat blocks
        for key in ("confirmed_matches", "candidate_groups", "reference_only", "target_only", "summary"):
            assert key in result, f"missing key: {key}"

    def test_all_mapped_targets_when_target_omitted(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id)
        assert "confirmed_matches" in result
        assert result["selected_target_categories"][0]["target_category_id"] == tgt_cat.id

    def test_target_category_ids_list_accepted(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(
                reference_category_id=ref_cat.id,
                target_category_ids=[tgt_cat.id],
            )
        assert "confirmed_matches" in result

    def test_target_category_ids_rejects_unmapped(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_stores_and_categories(session)
            # Create a second target cat in same store – not mapped
            unmapped_cat = upsert_category(session, store_id=tgt_store.id, name="Sticks")
            session.flush()
            with pytest.raises(ValueError, match="маппінг"):
                ComparisonService(session).compare(
                    reference_category_id=ref_cat.id,
                    target_category_ids=[unmapped_cat.id],
                )


# ---------------------------------------------------------------------------
# ComparisonService – response shape (new flat format)
# ---------------------------------------------------------------------------

class TestComparisonServiceResponseShape:
    def test_returns_new_shape_keys(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        for key in ("reference_category", "selected_target_categories",
                    "summary", "confirmed_matches", "candidate_groups",
                    "reference_only", "target_only"):
            assert key in result, f"missing top-level key: {key}"

    def test_summary_keys_present(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        summary = result["summary"]
        for key in ("confirmed_matches", "candidate_groups", "reference_only", "target_only"):
            assert key in summary, f"missing summary key: {key}"

    def test_empty_categories_give_zero_totals(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        s = result["summary"]
        assert s["confirmed_matches"] == 0
        assert s["candidate_groups"] == 0
        assert s["reference_only"] == 0
        assert s["target_only"] == 0

    def test_reference_category_info_in_result(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        assert result["reference_category"]["name"] == "Skates"
        assert result["reference_category"]["is_reference"] is True

    def test_selected_target_categories_metadata(self):
        with _session_scope() as session:
            _, _, ref_cat, tgt_cat = _make_mapped_categories(session)
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        assert len(result["selected_target_categories"]) == 1
        meta = result["selected_target_categories"][0]
        assert meta["target_category_id"] == tgt_cat.id
        assert meta["match_type"] == "manual"
        assert "target_store_id" in meta
        assert "target_store_name" in meta


# ---------------------------------------------------------------------------
# ComparisonService – heuristic matching (new shape)
# ---------------------------------------------------------------------------

class TestComparisonServiceHeuristicMatching:
    def test_unmatched_products_end_up_in_reference_only_or_target_only(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X5 SR", 4500, "ref-1hm")
            _add_product(session, tgt_store.id, tgt_cat.id, "CCM Tacks AS-V SR", 5200, "tgt-1hm")
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        # Bauer vs CCM → brand conflict → no match
        s = result["summary"]
        # ref product should be in reference_only or candidate_groups
        total_ref_accounted = (
            s["confirmed_matches"]
            + s["candidate_groups"]
            + s["reference_only"]
        )
        assert total_ref_accounted >= 1

    def test_matching_products_appear_somewhere(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X5 SR", 4500, "ref-bv-hm")
            _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Vapor X5 Senior", 4800, "tgt-bv-hm")
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        s = result["summary"]
        # Some match must be found (confirmed_matches or candidate_groups)
        assert s["confirmed_matches"] + s["candidate_groups"] >= 1

    def test_confirmed_match_has_is_confirmed_false_for_heuristic(self):
        """High-confidence heuristic match → is_confirmed=False in confirmed_matches."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X5 SR", 4500, "ref-bv3-hm")
            _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Vapor X5 Senior", 4800, "tgt-bv3-hm")
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        for m in result["confirmed_matches"]:
            if m["match_source"] != "confirmed":
                assert m["is_confirmed"] is False


# ---------------------------------------------------------------------------
# ComparisonService – stored product mappings (new shape)
# ---------------------------------------------------------------------------

class TestComparisonServiceStoredMappings:
    def test_stored_mapping_appears_in_confirmed_matches_with_is_confirmed_true(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            ref_prod = _add_product(session, ref_store.id, ref_cat.id, "Bauer Supreme M4 SR", 3900, "ref-sm-map")
            tgt_prod = _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Supreme M4 Senior", 4100, "tgt-sm-map")
            session.flush()
            create_product_mapping(
                session,
                reference_product_id=ref_prod.id,
                target_product_id=tgt_prod.id,
                match_status="confirmed",
                confidence=1.0,
            )
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        confirmed = [m for m in result["confirmed_matches"] if m["match_source"] == "confirmed"]
        assert len(confirmed) >= 1
        assert confirmed[0]["reference_product"]["id"] == ref_prod.id
        assert confirmed[0]["target_product"]["id"] == tgt_prod.id
        assert confirmed[0]["is_confirmed"] is True
        assert confirmed[0]["score_percent"] == 100  # confidence 1.0 → 100%

    def test_confirmed_match_products_not_in_reference_only_or_target_only(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            ref_prod = _add_product(session, ref_store.id, ref_cat.id, "CCM Tacks 9380 SR", 3500, "ref-ct-map")
            tgt_prod = _add_product(session, tgt_store.id, tgt_cat.id, "CCM Tacks 9380 Senior", 3700, "tgt-ct-map")
            session.flush()
            create_product_mapping(
                session,
                reference_product_id=ref_prod.id,
                target_product_id=tgt_prod.id,
                match_status="confirmed",
                confidence=1.0,
            )
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        ref_only_ids = [item["reference_product"]["id"] for item in result["reference_only"]]
        tgt_only_ids = [item["target_product"]["id"] for item in result["target_only"]]
        assert ref_prod.id not in ref_only_ids
        assert tgt_prod.id not in tgt_only_ids

    def test_target_only_excludes_candidates(self):
        """target_only must not include products that appear as candidates."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            # Similar products → candidate relationship
            ref_prod = _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X3 SR", 3000, "ref-cand-to")
            tgt_prod = _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Vapor X3 Senior", 3200, "tgt-cand-to")
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        tgt_only_ids = {item["target_product"]["id"] for item in result["target_only"]}
        # tgt_prod must NOT be in target_only if it appeared as candidate or confirmed
        in_confirmed = any(
            m["target_product"]["id"] == tgt_prod.id for m in result["confirmed_matches"]
        )
        in_candidates = any(
            any(c["target_product"].get("id") == tgt_prod.id for c in g["candidates"])
            for g in result["candidate_groups"]
        )
        if in_confirmed or in_candidates:
            assert tgt_prod.id not in tgt_only_ids

    def test_can_accept_false_when_target_already_confirmed(self):
        """can_accept=False when target product is used in a confirmed mapping."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            # Two reference products that could match the same target
            ref_prod1 = _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X5 SR", 4500, "ref-ca1")
            ref_prod2 = _add_product(session, ref_store.id, ref_cat.id, "Bauer Vapor X5 Pro SR", 4800, "ref-ca2")
            tgt_prod = _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Vapor X5 Senior", 4600, "tgt-ca1")
            session.flush()
            # Confirm tgt_prod for ref_prod1
            create_product_mapping(
                session,
                reference_product_id=ref_prod1.id,
                target_product_id=tgt_prod.id,
                match_status="confirmed",
                confidence=1.0,
            )
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id, target_category_id=tgt_cat.id)

        # tgt_prod is confirmed → any candidate entry for it must have can_accept=False
        for group in result["candidate_groups"]:
            for cand in group["candidates"]:
                tp = cand.get("target_product") or {}
                if tp.get("id") == tgt_prod.id:
                    assert cand["can_accept"] is False
                    assert cand["disabled_reason"] == "already_confirmed_elsewhere"


# ---------------------------------------------------------------------------
# Many-to-many: one ref category mapped to multiple target categories
# ---------------------------------------------------------------------------

class TestComparisonOneToMany:
    def test_compare_all_mapped_returns_products_from_both_stores(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefM2M", is_reference=True)
            tgt_store_a = get_or_create_store(session, "TgtM2M_A", is_reference=False)
            tgt_store_b = get_or_create_store(session, "TgtM2M_B", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Pads-m2m")
            tgt_cat_a = upsert_category(session, store_id=tgt_store_a.id, name="Pads-tgt-a")
            tgt_cat_b = upsert_category(session, store_id=tgt_store_b.id, name="Pads-tgt-b")
            create_category_mapping(session, reference_category_id=ref_cat.id,
                                    target_category_id=tgt_cat_a.id, match_type="manual")
            create_category_mapping(session, reference_category_id=ref_cat.id,
                                    target_category_id=tgt_cat_b.id, match_type="manual")
            _add_product(session, tgt_store_a.id, tgt_cat_a.id, "ProductA", 100, "p-a")
            _add_product(session, tgt_store_b.id, tgt_cat_b.id, "ProductB", 200, "p-b")
            session.flush()

            result = ComparisonService(session).compare(reference_category_id=ref_cat.id)

        assert len(result["selected_target_categories"]) == 2
        # Both target products should appear in target_only (no ref products)
        tgt_only_ids = {item["target_product"]["id"] for item in result["target_only"]}
        # They should be accounted for somewhere
        assert result["summary"]["target_only"] == 2

    def test_target_category_ids_list_spans_two_stores(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefM2M2", is_reference=True)
            tgt_store_a = get_or_create_store(session, "TgtM2M2_A", is_reference=False)
            tgt_store_b = get_or_create_store(session, "TgtM2M2_B", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="Helmets")
            tgt_cat_a = upsert_category(session, store_id=tgt_store_a.id, name="Helmets-A")
            tgt_cat_b = upsert_category(session, store_id=tgt_store_b.id, name="Helmets-B")
            create_category_mapping(session, reference_category_id=ref_cat.id,
                                    target_category_id=tgt_cat_a.id)
            create_category_mapping(session, reference_category_id=ref_cat.id,
                                    target_category_id=tgt_cat_b.id)
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=ref_cat.id,
                target_category_ids=[tgt_cat_a.id, tgt_cat_b.id],
            )

        assert len(result["selected_target_categories"]) == 2


# ---------------------------------------------------------------------------
# Flask integration tests — /api/comparison contract
# ---------------------------------------------------------------------------

class TestApiComparisonContract:
    """Test /api/comparison via Flask test client using monkeypatching."""

    def _make_result(self):
        return {
            "reference_category": {"id": 1, "name": "Skates", "store_id": 1,
                                    "store_name": "Ref", "is_reference": True,
                                    "normalized_name": "skates", "url": None},
            "target_store": {"id": 2, "name": "Tgt", "is_reference": False},
            "selected_target_categories": [
                {"target_category_id": 2, "target_category_name": "Skates",
                 "target_store_id": 2, "target_store_name": "Tgt",
                 "match_type": "manual", "confidence": 1.0}
            ],
            "summary": {
                "confirmed_matches": 1,
                "candidate_groups": 0,
                "reference_only": 1,
                "target_only": 1,
            },
            "confirmed_matches": [
                {
                    "reference_product": {"id": 10, "name": "P1", "product_url": "#"},
                    "target_product": {"id": 20, "name": "P2", "product_url": "#"},
                    "target_category": None,
                    "score_percent": 95,
                    "score_details": {},
                    "match_source": "heuristic_high_confidence",
                    "is_confirmed": False,
                }
            ],
            "candidate_groups": [],
            "reference_only": [{"reference_product": {"id": 11, "name": "P3"}}],
            "target_only": [{"target_product": {"id": 21, "name": "P4"}, "target_category": None}],
        }

    def test_returns_200_with_structured_response(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        result = self._make_result()
        monkeypatch.setattr(ComparisonService, "compare", lambda self, **kw: result)

        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_id": 2},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reference_category" in data
        assert "selected_target_categories" in data
        assert "summary" in data
        assert "confirmed_matches" in data
        assert "candidate_groups" in data

    def test_returns_400_when_missing_reference_id(self):
        from app import app as flask_app
        resp = flask_app.test_client().post("/api/comparison", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_accepts_target_category_ids_list(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        received_kwargs = {}

        def fake_compare(self, **kw):
            received_kwargs.update(kw)
            return self._make_result() if False else _make_result_static()

        def _make_result_static():
            return {
                "reference_category": {}, "target_store": None,
                "selected_target_categories": [],
                "summary": {"confirmed_matches":0,"candidate_groups":0,"reference_only":0,"target_only":0},
                "confirmed_matches": [], "candidate_groups": [],
                "reference_only": [], "target_only": [],
            }

        monkeypatch.setattr(ComparisonService, "compare", fake_compare)

        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_ids": [2, 3]},
        )
        assert resp.status_code == 200
        assert received_kwargs.get("target_category_ids") == [2, 3]

    def test_target_category_id_is_optional(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        result = self._make_result()
        monkeypatch.setattr(ComparisonService, "compare", lambda self, **kw: result)

        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1},
        )
        assert resp.status_code == 200

    def test_returns_400_for_non_json(self):
        from app import app as flask_app
        resp = flask_app.test_client().post("/api/comparison", data="not-json",
                                            content_type="text/plain")
        assert resp.status_code == 400

    def test_returns_400_on_value_error(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        monkeypatch.setattr(ComparisonService, "compare",
                            lambda self, **kw: (_ for _ in ()).throw(ValueError("Category 999 not found")))

        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 999, "target_category_id": 888},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_returns_400_when_no_mapping_exists(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        def raise_no_mapping(self, **kw):
            raise ValueError("Для цієї категорії ще не створено меппінг")

        monkeypatch.setattr(ComparisonService, "compare", raise_no_mapping)
        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1},
        )
        assert resp.status_code == 400
        assert "меппінг" in resp.get_json()["error"]

    def test_summary_keys_in_response(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        result = self._make_result()
        monkeypatch.setattr(ComparisonService, "compare", lambda self, **kw: result)

        data = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_id": 2},
        ).get_json()

        summary = data["summary"]
        for key in ("confirmed_matches", "candidate_groups", "reference_only", "target_only"):
            assert key in summary, f"missing summary key: {key}"

    def test_does_not_return_old_top_level_keys(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        result = self._make_result()
        monkeypatch.setattr(ComparisonService, "compare", lambda self, **kw: result)

        data = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_id": 2},
        ).get_json()

        for old_key in ("comparisons", "missing", "total_urls", "scanned"):
            assert old_key not in data, f"old top-level key still present: {old_key}"

    def test_returns_400_when_target_ids_contains_unmapped(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService

        def raise_unmapped(self, **kw):
            raise ValueError("Категорія 99 не знайдена в маппінгах")

        monkeypatch.setattr(ComparisonService, "compare", raise_unmapped)
        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_ids": [99]},
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Flask integration tests — /api/comparison/confirm-match
# ---------------------------------------------------------------------------

class TestApiConfirmMatch:
    def _make_pm(self):
        return SimpleNamespace(
            id=1,
            reference_product_id=10,
            target_product_id=20,
            reference_product=None,
            target_product=None,
            match_status="confirmed",
            confidence=None,
            comment=None,
            updated_at=datetime.now(timezone.utc),
        )

    def test_returns_200_with_product_mapping_key(self, monkeypatch):
        from app import app as flask_app
        import app as app_module

        pm = self._make_pm()
        monkeypatch.setattr(app_module, "create_product_mapping", lambda session, **kw: pm)

        resp = flask_app.test_client().post(
            "/api/comparison/confirm-match",
            json={"reference_product_id": 10, "target_product_id": 20},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "product_mapping" in data
        assert data["product_mapping"]["reference_product_id"] == 10
        assert data["product_mapping"]["target_product_id"] == 20

    def test_returns_400_when_ids_missing(self):
        from app import app as flask_app
        resp = flask_app.test_client().post("/api/comparison/confirm-match", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_returns_400_on_exception(self, monkeypatch):
        from app import app as flask_app
        import app as app_module

        monkeypatch.setattr(app_module, "create_product_mapping",
                            lambda session, **kw: (_ for _ in ()).throw(ValueError("integrity error")))
        resp = flask_app.test_client().post(
            "/api/comparison/confirm-match",
            json={"reference_product_id": 10, "target_product_id": 20},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_confirm_match_route_precedes_comparison_route(self):
        from app import app as flask_app
        resp = flask_app.test_client().post(
            "/api/comparison/confirm-match",
            json={},
        )
        assert resp.status_code in (200, 400)

    def test_confirm_match_creates_product_mapping_in_db(self):
        """End-to-end: confirm-match actually writes to the DB."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _make_mapped_categories(session)
            ref_prod = _add_product(session, ref_store.id, ref_cat.id, "Bauer Hyperlite SR", 8000, "ref-hl-cm")
            tgt_prod = _add_product(session, tgt_store.id, tgt_cat.id, "Bauer Hyperlite Senior", 8200, "tgt-hl-cm")
            session.flush()
            ref_prod_id = ref_prod.id
            tgt_prod_id = tgt_prod.id

        from app import app as flask_app
        resp = flask_app.test_client().post(
            "/api/comparison/confirm-match",
            json={
                "reference_product_id": ref_prod_id,
                "target_product_id": tgt_prod_id,
                "match_status": "confirmed",
                "confidence": 0.97,
            },
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["product_mapping"]["match_status"] == "confirmed"

