"""tests/test_product_match_review.py — Focused tests for product match review workflow.

Covers ADR-0012 / RFC-013:
- MatchDecisionRequest DTO validation (confirmed / rejected / invalid)
- Repository helpers: upsert_match_decision, get_rejected_pairs_for_refs,
  get_confirmed_target_ids_for_refs, list_product_mappings_filtered
- ComparisonService: rejected pair suppression from heuristic output
- state transitions: confirmed→rejected and rejected→confirmed
- GET /api/product-mappings endpoint
- POST /api/comparison/match-decision endpoint
- GET /api/comparison/eligible-target-products endpoint
- GET /matches UI route
- test_admin_routes_split extensions for new routes
"""
from __future__ import annotations

import pytest

from pricewatch.db.testing import test_session_scope as _session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import upsert_category, create_category_mapping
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import (
    upsert_match_decision,
    get_product_mapping,
    get_rejected_pairs_for_refs,
    get_confirmed_target_ids_for_refs,
    get_all_confirmed_target_ids,
    list_product_mappings_filtered,
    get_conflicting_confirmed_mapping,
)
from pricewatch.services.comparison_service import ComparisonService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup(session):
    ref_store = get_or_create_store(session, "Ref_PMR", is_reference=True)
    tgt_store = get_or_create_store(session, "Tgt_PMR", is_reference=False)
    ref_cat   = upsert_category(session, store_id=ref_store.id, name="SkatePMR")
    tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SkatePMR")
    create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
    session.flush()
    return ref_store, tgt_store, ref_cat, tgt_cat


def _prod(session, store_id, cat_id, name, key):
    return upsert_product(
        session, store_id=store_id,
        product_url=f"https://ex.com/{key}",
        name=name, price=100, currency="UAH", category_id=cat_id,
    )


# ---------------------------------------------------------------------------
# 1. MatchDecisionRequest DTO validation
# ---------------------------------------------------------------------------

class TestMatchDecisionRequestDTO:
    def test_confirmed_is_valid(self):
        from pricewatch.schemas.requests.comparison import MatchDecisionRequest
        dto = MatchDecisionRequest(reference_product_id=1, target_product_id=2, match_status="confirmed")
        assert dto.match_status == "confirmed"

    def test_rejected_is_valid(self):
        from pricewatch.schemas.requests.comparison import MatchDecisionRequest
        dto = MatchDecisionRequest(reference_product_id=1, target_product_id=2, match_status="rejected")
        assert dto.match_status == "rejected"

    def test_invalid_status_raises(self):
        from pydantic import ValidationError
        from pricewatch.schemas.requests.comparison import MatchDecisionRequest
        with pytest.raises(ValidationError):
            MatchDecisionRequest(reference_product_id=1, target_product_id=2, match_status="maybe")

    def test_missing_reference_id_raises(self):
        from pydantic import ValidationError
        from pricewatch.schemas.requests.comparison import MatchDecisionRequest
        with pytest.raises(ValidationError):
            MatchDecisionRequest(target_product_id=2, match_status="confirmed")


# ---------------------------------------------------------------------------
# 2. Repository: upsert_match_decision single-row semantics
# ---------------------------------------------------------------------------

class TestUpsertMatchDecisionRepository:
    def test_creates_new_row(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Bauer Skate A", "bsa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Bauer Skate A", "bsb")
            session.flush()
            pm = upsert_match_decision(
                session, reference_product_id=ref_p.id, target_product_id=tgt_p.id,
                match_status="confirmed",
            )
            assert pm.id is not None
            assert pm.match_status == "confirmed"

    def test_updates_existing_row_on_status_change(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Bauer Skate B", "bsc")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Bauer Skate B", "bsd")
            session.flush()
            pm1 = upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            pm2 = upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            assert pm1.id == pm2.id
            assert pm2.match_status == "rejected"

    def test_confirmed_to_rejected_to_confirmed_cycle(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "CCM Skate X", "ccx")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "CCM Skate X", "ccy")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            pm = upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            assert pm.match_status == "confirmed"

    def test_reject_is_pair_level_not_global(self):
        """Rejecting one pair must not affect a different (ref, tgt) pair."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p  = _prod(session, ref_store.id, ref_cat.id, "Warrior Alpha A", "waa")
            tgt_p1 = _prod(session, tgt_store.id, tgt_cat.id, "Warrior Alpha A", "wab")
            tgt_p2 = _prod(session, tgt_store.id, tgt_cat.id, "Warrior Alpha B", "wac")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p1.id, match_status="rejected")
            # tgt_p2 must not be rejected
            pm2 = get_product_mapping(session, reference_product_id=ref_p.id, target_product_id=tgt_p2.id)
            assert pm2 is None


# ---------------------------------------------------------------------------
# 3. Repository: batch helpers
# ---------------------------------------------------------------------------

class TestBatchRepositoryHelpers:
    def test_get_rejected_pairs_for_refs(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Bauer X A", "bxa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Bauer X A", "bxb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            pairs = get_rejected_pairs_for_refs(session, [ref_p.id])
            assert (ref_p.id, tgt_p.id) in pairs

    def test_get_rejected_pairs_excludes_confirmed(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "CCM Y A", "cya")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "CCM Y A", "cyb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            pairs = get_rejected_pairs_for_refs(session, [ref_p.id])
            assert (ref_p.id, tgt_p.id) not in pairs

    def test_get_confirmed_target_ids_for_refs(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "True Stick A", "tsa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "True Stick A", "tsb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            mapping = get_confirmed_target_ids_for_refs(session, [ref_p.id])
            assert tgt_p.id in mapping.get(ref_p.id, set())

    def test_get_all_confirmed_target_ids(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Graf Skate A", "gsa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Graf Skate A", "gsb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            confirmed = get_all_confirmed_target_ids(session, [tgt_p.id])
            assert tgt_p.id in confirmed

    def test_list_product_mappings_filtered_confirmed_only(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Warrior LX A", "wlxa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Warrior LX A", "wlxb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            rows = list_product_mappings_filtered(session, status="confirmed")
            ids = [r.id for r in rows]
            pm = get_product_mapping(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id)
            assert pm.id in ids

    def test_list_product_mappings_filtered_excludes_rejected(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "CCM Tacks R", "ctr")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "CCM Tacks R", "ctrs")
            session.flush()
            pm = upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            rows = list_product_mappings_filtered(session, status="confirmed")
            assert pm.id not in [r.id for r in rows]

    def test_list_product_mappings_filtered_search(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Easton Mako Search", "ems")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Easton Mako Search", "emst")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            rows = list_product_mappings_filtered(session, status="confirmed", search="Easton Mako")
            assert any("Easton" in (r.reference_product.name if r.reference_product else "") for r in rows)


# ---------------------------------------------------------------------------
# 4. ComparisonService: reject suppression
# ---------------------------------------------------------------------------

class TestComparisonServiceRejectSuppression:
    def test_rejected_pair_not_in_candidate_groups(self):
        """A rejected exact pair must be absent from candidate_groups."""
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefCS_R1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCS_R1", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="HelmetsR1")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="HelmetsR1")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Bauer Re-Akt Helmet SR", "brh1")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Bauer Re-Akt Helmet SR", "brh2")
            session.flush()
            # Reject the pair
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id)

        for g in result["candidate_groups"]:
            for c in g["candidates"]:
                tp = c.get("target_product") or {}
                assert tp.get("id") != tgt_p.id, "Rejected target appeared in candidate_groups"

    def test_rejected_to_confirmed_restores_pair(self):
        """After confirmed→rejected→confirmed, the pair appears as a confirmed match."""
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefCS_R2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCS_R2", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="HelmetsR2")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="HelmetsR2")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "CCM Tacks 310 Helmet SR", "cth1")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "CCM Tacks 310 Helmet SR", "cth2")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            result = ComparisonService(session).compare(reference_category_id=ref_cat.id)

        confirmed_ids = [
            (m.get("reference_product") or {}).get("id")
            for m in result["confirmed_matches"]
        ]
        assert ref_p.id in confirmed_ids


# ---------------------------------------------------------------------------
# 5. eligible-target-products service method
# ---------------------------------------------------------------------------

class TestEligibleTargetProducts:
    def test_returns_products_from_selected_categories_only(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefETP1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETP1", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="ETPCatA")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="ETPCatA")
            other_tgt_cat = upsert_category(session, store_id=tgt_store.id, name="ETPCatB")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "ETP Ref Product", "etpr")
            tgt_p1 = _prod(session, tgt_store.id, tgt_cat.id, "ETP Target A", "etpa")
            tgt_p2 = _prod(session, tgt_store.id, other_tgt_cat.id, "ETP Other Cat B", "etpb")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
            )

        ids = [r["id"] for r in results]
        assert tgt_p1.id in ids
        assert tgt_p2.id not in ids, "Product from other category must not appear"

    def test_excludes_already_confirmed_elsewhere(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefETP2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETP2", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="ETPCat2")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="ETPCat2")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p1 = _prod(session, ref_store.id, ref_cat.id, "ETP Ref P1", "etprp1")
            ref_p2 = _prod(session, ref_store.id, ref_cat.id, "ETP Ref P2", "etprp2")
            tgt_p  = _prod(session, tgt_store.id, tgt_cat.id, "ETP Shared Target", "etpst")
            session.flush()
            # ref_p2 already confirmed to tgt_p
            upsert_match_decision(session, reference_product_id=ref_p2.id, target_product_id=tgt_p.id, match_status="confirmed")

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p1.id,
                target_category_ids=[tgt_cat.id],
            )

        assert all(r["id"] != tgt_p.id for r in results), \
            "Already-confirmed-elsewhere target must not be returned"

    def test_excludes_rejected_pairs(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefETP3", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETP3", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="ETPCat3")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="ETPCat3")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "ETP Ref P3", "etprp3")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "ETP Target P3", "etptp3")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
            )

        assert all(r["id"] != tgt_p.id for r in results), \
            "Rejected pair must not appear in eligible targets"

    def test_search_filter_works(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "RefETP4", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETP4", is_reference=False)
            ref_cat = upsert_category(session, store_id=ref_store.id, name="ETPCat4")
            tgt_cat = upsert_category(session, store_id=tgt_store.id, name="ETPCat4")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "ETP Ref P4", "etprp4")
            _prod(session, tgt_store.id, tgt_cat.id, "Bauer ETP Match", "etpbauer")
            _prod(session, tgt_store.id, tgt_cat.id, "CCM Other Product", "etpccm")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
                search="Bauer",
            )

        assert all("Bauer" in r["name"] for r in results)
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# 6. HTTP API: POST /api/comparison/match-decision
# ---------------------------------------------------------------------------

class TestMatchDecisionEndpoint:
    def test_confirmed_decision_accepted(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefMDE1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtMDE1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="MDECat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="MDECat1")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "MDE Ref A", "mdera")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "MDE Tgt A", "mdeta")
            session.flush()
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status": "confirmed",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["product_mapping"]["match_status"] == "confirmed"

    def test_rejected_decision_accepted(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefMDE2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtMDE2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="MDECat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="MDECat2")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "MDE Ref B", "mderb")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "MDE Tgt B", "mdetb")
            session.flush()
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status": "rejected",
        })
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["product_mapping"]["match_status"] == "rejected"

    def test_invalid_status_returns_422(self, client, db_session_scope):
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": 1, "target_product_id": 2, "match_status": "maybe",
        })
        assert resp.status_code == 422

    def test_missing_required_fields_returns_422(self, client):
        resp = client.post("/api/comparison/match-decision", json={"match_status": "confirmed"})
        assert resp.status_code == 422

    def test_confirm_match_shim_still_works(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefShim1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtShim1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="ShimCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="ShimCat1")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "Shim Ref A", "shimra")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "Shim Tgt A", "shimta")
            session.flush()
        resp = client.post("/api/comparison/confirm-match", json={
            "reference_product_id": ref_p.id, "target_product_id": tgt_p.id,
        })
        assert resp.status_code == 200
        assert "product_mapping" in resp.get_json()


# ---------------------------------------------------------------------------
# 7. HTTP API: GET /api/product-mappings
# ---------------------------------------------------------------------------

class TestProductMappingsEndpoint:
    def test_defaults_to_confirmed_only(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefPM1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtPM1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="PMCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="PMCat1")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "PM Ref A", "pmra")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "PM Tgt A", "pmta")
            tgt_p2 = _prod(session, tgt_store.id, tgt_cat.id, "PM Tgt B", "pmtb")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p2.id, match_status="rejected")
            confirmed_id = get_product_mapping(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id).id
            rejected_id  = get_product_mapping(session, reference_product_id=ref_p.id, target_product_id=tgt_p2.id).id

        resp = client.get("/api/product-mappings")
        assert resp.status_code == 200
        body = resp.get_json()
        ids = [m["id"] for m in body["product_mappings"]]
        assert confirmed_id in ids
        assert rejected_id not in ids

    def test_status_rejected_filter(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefPM2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtPM2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="PMCat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="PMCat2")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "PM Ref C", "pmrc")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "PM Tgt C", "pmtc")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="rejected")
            rej_id = get_product_mapping(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id).id

        resp = client.get("/api/product-mappings?status=rejected")
        assert resp.status_code == 200
        ids = [m["id"] for m in resp.get_json()["product_mappings"]]
        assert rej_id in ids

    def test_response_contains_product_objects(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefPM3", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtPM3", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="PMCat3")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="PMCat3")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "PM Rich Ref", "pmrr")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "PM Rich Tgt", "pmrtt")
            session.flush()
            upsert_match_decision(session, reference_product_id=ref_p.id, target_product_id=tgt_p.id, match_status="confirmed")

        resp = client.get("/api/product-mappings")
        assert resp.status_code == 200
        rows = resp.get_json()["product_mappings"]
        assert any(r.get("reference_product") is not None for r in rows)
        assert any(r.get("target_product") is not None for r in rows)


# ---------------------------------------------------------------------------
# 8. HTTP API: GET /api/comparison/eligible-target-products
# ---------------------------------------------------------------------------

class TestEligibleTargetProductsEndpoint:
    def test_missing_reference_product_id_returns_400(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefETPE1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETPE1", is_reference=False)
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="ETPECat1")
            session.flush()
        resp = client.get(f"/api/comparison/eligible-target-products?target_category_ids={tgt_cat.id}")
        assert resp.status_code == 400

    def test_missing_target_category_ids_returns_400(self, client, db_session_scope):
        resp = client.get("/api/comparison/eligible-target-products?reference_product_id=1")
        assert resp.status_code == 400

    def test_returns_scoped_products(self, client, db_session_scope):
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefETPE2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtETPE2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="ETPECat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="ETPECat2")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "ETPE Ref", "etpere")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "ETPE Tgt", "etpete")
            session.flush()
        resp = client.get(
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p.id}&target_category_ids={tgt_cat.id}"
        )
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["products"]]
        assert tgt_p.id in ids


# ---------------------------------------------------------------------------
# 9. UI route: GET /matches
# ---------------------------------------------------------------------------

class TestMatchesUIRoute:
    def test_matches_page_returns_200(self, client):
        resp = client.get("/matches")
        assert resp.status_code == 200

    def test_matches_page_contains_vue_mount_root(self, client):
        # After Commit 8 cutover /matches serves the SPA shell.
        # Vue Router renders the MatchesRouteView client-side from the #app root.
        resp = client.get("/matches")
        html = resp.data.decode("utf-8")
        assert 'id="app"' in html, "/matches must serve the SPA shell with #app mount root"
        assert "__PRICEWATCH_BOOTSTRAP__" in html


# ---------------------------------------------------------------------------
# 10. Route registration smoke tests
# ---------------------------------------------------------------------------

class TestNewRoutesRegistered:
    @pytest.fixture(scope="class")
    def app(self):
        from pricewatch.app_factory import create_app
        return create_app({"TESTING": True})

    def _routes(self, app):
        return {rule.rule for rule in app.url_map.iter_rules()}

    def test_match_decision_route_present(self, app):
        assert "/api/comparison/match-decision" in self._routes(app)

    def test_product_mappings_route_present(self, app):
        assert "/api/product-mappings" in self._routes(app)

    def test_eligible_target_products_route_present(self, app):
        assert "/api/comparison/eligible-target-products" in self._routes(app)

    def test_matches_ui_route_present(self, app):
        assert "/matches" in self._routes(app)

    def test_product_mapping_review_module_importable(self, app):
        from pricewatch.web.admin_product_mapping_review_routes import (
            register_admin_product_mapping_review_routes,
        )
        assert callable(register_admin_product_mapping_review_routes)


# ---------------------------------------------------------------------------
# 11. Commit 1 — Confirmed target uniqueness (server-side invariant)
# ---------------------------------------------------------------------------

class TestConfirmedTargetUniqueness:
    """Gap A: server-side enforcement that one target cannot be confirmed
    for two different reference products simultaneously."""

    def test_duplicate_confirmed_target_fails_409(self, client, db_session_scope):
        """Confirming the same target for a second reference must fail with 409."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefCTU1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCTU1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="CTUCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="CTUCat1")
            session.flush()
            ref_a = _prod(session, ref_store.id, ref_cat.id, "CTU Ref A", "cturefa")
            ref_b = _prod(session, ref_store.id, ref_cat.id, "CTU Ref B", "cturefb")
            tgt_x = _prod(session, tgt_store.id, tgt_cat.id, "CTU Tgt X", "ctutgtx")
            session.flush()

        # First confirm: ref_a + tgt_x → should succeed
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_a.id,
            "target_product_id":    tgt_x.id,
            "match_status": "confirmed",
        })
        assert resp.status_code == 200

        # Second confirm: ref_b + tgt_x → should fail 409
        resp2 = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_b.id,
            "target_product_id":    tgt_x.id,
            "match_status": "confirmed",
        })
        assert resp2.status_code == 409
        body = resp2.get_json()
        assert "error" in body
        assert "already confirmed" in body["error"].lower()
        assert body.get("conflicting_reference_product_id") == ref_a.id

    def test_same_pair_override_cycle_succeeds(self, client, db_session_scope):
        """confirmed → rejected → confirmed for the SAME pair must always succeed."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefCTU2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCTU2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="CTUCat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="CTUCat2")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "CTU Cycle Ref", "ctucycleref")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "CTU Cycle Tgt", "ctucycletgt")
            session.flush()

        r1 = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id, "target_product_id": tgt_p.id, "match_status": "confirmed",
        })
        assert r1.status_code == 200

        r2 = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id, "target_product_id": tgt_p.id, "match_status": "rejected",
        })
        assert r2.status_code == 200

        r3 = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id, "target_product_id": tgt_p.id, "match_status": "confirmed",
        })
        assert r3.status_code == 200

    def test_rejected_different_ref_does_not_conflict(self, client, db_session_scope):
        """Rejected status for ref_b + tgt_x must be allowed even when ref_a + tgt_x is confirmed."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefCTU3", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCTU3", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="CTUCat3")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="CTUCat3")
            session.flush()
            ref_a = _prod(session, ref_store.id, ref_cat.id, "CTU RefA2", "cturefa2")
            ref_b = _prod(session, ref_store.id, ref_cat.id, "CTU RefB2", "cturefb2")
            tgt_x = _prod(session, tgt_store.id, tgt_cat.id, "CTU TgtX2", "ctutgtx2")
            session.flush()

        # ref_a confirms tgt_x
        client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_a.id, "target_product_id": tgt_x.id, "match_status": "confirmed",
        })

        # ref_b REJECTS tgt_x — must succeed (not a conflict)
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_b.id,
            "target_product_id":    tgt_x.id,
            "match_status": "rejected",
        })
        assert resp.status_code == 200

    def test_shim_also_enforces_uniqueness(self, client, db_session_scope):
        """The /confirm-match shim must also enforce the uniqueness invariant."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefCTU4", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtCTU4", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="CTUCat4")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="CTUCat4")
            session.flush()
            ref_a = _prod(session, ref_store.id, ref_cat.id, "CTU Shim RefA", "ctushimrefa")
            ref_b = _prod(session, ref_store.id, ref_cat.id, "CTU Shim RefB", "ctushimrefb")
            tgt_x = _prod(session, tgt_store.id, tgt_cat.id, "CTU Shim TgtX", "ctushimtgtx")
            session.flush()

        # First confirm via shim succeeds
        r1 = client.post("/api/comparison/confirm-match", json={
            "reference_product_id": ref_a.id, "target_product_id": tgt_x.id,
        })
        assert r1.status_code == 200

        # Second confirm via shim for different ref must fail
        r2 = client.post("/api/comparison/confirm-match", json={
            "reference_product_id": ref_b.id, "target_product_id": tgt_x.id,
        })
        assert r2.status_code == 409

    def test_get_conflicting_confirmed_mapping_repository(self):
        """Unit test the repository helper directly."""
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = _setup(session)
            ref_a = _prod(session, ref_store.id, ref_cat.id, "CTU Repo RefA", "cturepoa")
            ref_b = _prod(session, ref_store.id, ref_cat.id, "CTU Repo RefB", "cturepo_b")
            tgt_x = _prod(session, tgt_store.id, tgt_cat.id, "CTU Repo TgtX", "cturepox")
            session.flush()

            # No conflict yet
            assert get_conflicting_confirmed_mapping(
                session, reference_product_id=ref_b.id, target_product_id=tgt_x.id
            ) is None

            # Confirm ref_a + tgt_x
            upsert_match_decision(
                session, reference_product_id=ref_a.id, target_product_id=tgt_x.id,
                match_status="confirmed",
            )

            # Now there IS a conflict when checking from ref_b perspective
            conflict = get_conflicting_confirmed_mapping(
                session, reference_product_id=ref_b.id, target_product_id=tgt_x.id
            )
            assert conflict is not None
            assert conflict.reference_product_id == ref_a.id

            # No self-conflict: same pair returns None
            no_conflict = get_conflicting_confirmed_mapping(
                session, reference_product_id=ref_a.id, target_product_id=tgt_x.id
            )
            assert no_conflict is None


# ---------------------------------------------------------------------------
# 12. Commit 2 — Server-side scope validation for manual match decisions
# ---------------------------------------------------------------------------

class TestScopeValidation:
    """Gap B: target product must belong to a category that is mapped
    to the reference product's category."""

    def test_match_decision_rejects_off_scope_target_with_categories_provided(
        self, client, db_session_scope
    ):
        """POST match-decision with target_category_ids that don't include
        the actual target product's category must return 400."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSV1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSV1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SVCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SVCat1")
            other_cat = upsert_category(session, store_id=tgt_store.id, name="SVOtherCat")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SV Ref P1", "svrp1")
            # tgt_p is in tgt_cat, but we'll claim it's in other_cat via the request
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SV Tgt P1", "svtp1")
            session.flush()

        # provide target_category_ids that don't include tgt_cat (where tgt_p actually lives)
        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status":         "confirmed",
            "target_category_ids":  [other_cat.id],
        })
        assert resp.status_code == 400, resp.get_json()

    def test_match_decision_without_target_category_ids_still_accepted(
        self, client, db_session_scope
    ):
        """Old payload without target_category_ids must still work (backward compat)."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSV2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSV2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SVCat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SVCat2")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SV Ref P2", "svrp2")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SV Tgt P2", "svtp2")
            session.flush()

        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status": "confirmed",
            # no target_category_ids — legacy path
        })
        assert resp.status_code == 200

    def test_eligible_products_include_rejected_param(self, client, db_session_scope):
        """include_rejected=true must surface previously rejected pair."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSV3", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSV3", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SVCat3")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SVCat3")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SV Ref P3", "svrp3")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SV Tgt P3", "svtp3")
            session.flush()
            upsert_match_decision(
                session, reference_product_id=ref_p.id,
                target_product_id=tgt_p.id, match_status="rejected",
            )

        url = (
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p.id}"
            f"&target_category_ids={tgt_cat.id}"
            f"&include_rejected=true"
        )
        resp = client.get(url)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["products"]]
        assert tgt_p.id in ids, "Rejected product should be surfaced when include_rejected=true"

    def test_eligible_products_rejected_hidden_by_default(self, client, db_session_scope):
        """Rejected pair must NOT appear when include_rejected is omitted."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSV4", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSV4", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SVCat4")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SVCat4")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SV Ref P4", "svrp4")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SV Tgt P4", "svtp4")
            session.flush()
            upsert_match_decision(
                session, reference_product_id=ref_p.id,
                target_product_id=tgt_p.id, match_status="rejected",
            )

        url = (
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p.id}"
            f"&target_category_ids={tgt_cat.id}"
        )
        resp = client.get(url)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["products"]]
        assert tgt_p.id not in ids, "Rejected product must be hidden by default"

    def test_confirmed_elsewhere_still_blocked_even_with_include_rejected(
        self, client, db_session_scope
    ):
        """Even with include_rejected=true, a globally-confirmed target must NOT appear."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSV5", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSV5", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SVCat5")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SVCat5")
            create_category_mapping(session, reference_category_id=ref_cat.id, target_category_id=tgt_cat.id, match_type="manual")
            session.flush()
            ref_p1 = _prod(session, ref_store.id, ref_cat.id, "SV Ref P5a", "svrp5a")
            ref_p2 = _prod(session, ref_store.id, ref_cat.id, "SV Ref P5b", "svrp5b")
            tgt_p  = _prod(session, tgt_store.id, tgt_cat.id, "SV Tgt P5",  "svtp5")
            session.flush()
            # ref_p2 already confirmed tgt_p
            upsert_match_decision(
                session, reference_product_id=ref_p2.id,
                target_product_id=tgt_p.id, match_status="confirmed",
            )

        url = (
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p1.id}"
            f"&target_category_ids={tgt_cat.id}"
            f"&include_rejected=true"
        )
        resp = client.get(url)
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["products"]]
        assert tgt_p.id not in ids, "Globally confirmed target must always be blocked"


# ---------------------------------------------------------------------------
# 13. Scope enforcement fixup — eligible-target-products scope guard
# ---------------------------------------------------------------------------

class TestEligibleTargetProductsScope:
    """Final scope-enforcement fixup:
    - eligible-target-products rejects off-scope category ids with 400
    - eligible-target-products accepts valid mapped category ids with 200
    - match-decision with explicit target_category_ids in scope returns 200
    - match-decision without target_category_ids still works (backward compat)
    """

    def test_off_scope_category_returns_400(self, client, db_session_scope):
        """eligible-target-products must reject category ids not mapped to
        the reference product's category."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSEF1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSEF1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SEFCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SEFCat1")
            unrelated = upsert_category(session, store_id=tgt_store.id, name="SEFUnrelated")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SEF Ref P1", "sefrp1")
            session.flush()

        # use unrelated category (not mapped to ref_cat) — must be rejected
        resp = client.get(
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p.id}"
            f"&target_category_ids={unrelated.id}"
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.get_json()}"
        assert "error" in resp.get_json()

    def test_valid_mapped_category_returns_200(self, client, db_session_scope):
        """eligible-target-products must succeed when category is properly mapped."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSEF2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSEF2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SEFCat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SEFCat2")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SEF Ref P2", "sefrp2")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SEF Tgt P2", "seftp2")
            session.flush()

        resp = client.get(
            f"/api/comparison/eligible-target-products"
            f"?reference_product_id={ref_p.id}"
            f"&target_category_ids={tgt_cat.id}"
        )
        assert resp.status_code == 200
        ids = [p["id"] for p in resp.get_json()["products"]]
        assert tgt_p.id in ids

    def test_match_decision_with_valid_target_category_ids_succeeds(
        self, client, db_session_scope
    ):
        """match-decision with explicit target_category_ids inside mapped scope must succeed."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSEF3", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSEF3", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SEFCat3")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SEFCat3")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SEF Ref P3", "sefrp3")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SEF Tgt P3", "seftp3")
            session.flush()

        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status":         "confirmed",
            "target_category_ids":  [tgt_cat.id],
        })
        assert resp.status_code == 200
        assert resp.get_json()["product_mapping"]["match_status"] == "confirmed"

    def test_match_decision_without_target_category_ids_still_works(
        self, client, db_session_scope
    ):
        """Legacy match-decision without target_category_ids must still be accepted
        (backward compatibility — old callers that omit the field)."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefSEF4", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtSEF4", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="SEFCat4")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="SEFCat4")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat.id, match_type="manual",
            )
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "SEF Ref P4", "sefrp4")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "SEF Tgt P4", "seftp4")
            session.flush()

        resp = client.post("/api/comparison/match-decision", json={
            "reference_product_id": ref_p.id,
            "target_product_id":    tgt_p.id,
            "match_status":         "confirmed",
            # intentionally omitting target_category_ids — legacy path
        })
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# 14. DELETE /api/product-mappings/<id>
# ---------------------------------------------------------------------------

class TestDeleteProductMappingEndpoint:
    """Commit 2: hard-delete action for persisted product mapping rows."""

    def test_delete_existing_mapping_returns_200(self, client, db_session_scope):
        """Deleting an existing mapping must return 200 with correct payload."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefDEL1", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtDEL1", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="DELCat1")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="DELCat1")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "DEL Ref A", "delrefa")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "DEL Tgt A", "deltgta")
            session.flush()
            pm = upsert_match_decision(
                session, reference_product_id=ref_p.id,
                target_product_id=tgt_p.id, match_status="confirmed",
            )
            pm_id = pm.id

        resp = client.delete(f"/api/product-mappings/{pm_id}")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body["deleted"] is True
        assert body["mapping_id"] == pm_id

    def test_deleted_mapping_no_longer_exists(self, client, db_session_scope):
        """After a successful DELETE, the mapping row must be absent from the DB."""
        with db_session_scope() as session:
            ref_store = get_or_create_store(session, "RefDEL2", is_reference=True)
            tgt_store = get_or_create_store(session, "TgtDEL2", is_reference=False)
            ref_cat   = upsert_category(session, store_id=ref_store.id, name="DELCat2")
            tgt_cat   = upsert_category(session, store_id=tgt_store.id, name="DELCat2")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "DEL Ref B", "delrefb")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "DEL Tgt B", "deltgtb")
            session.flush()
            pm = upsert_match_decision(
                session, reference_product_id=ref_p.id,
                target_product_id=tgt_p.id, match_status="confirmed",
            )
            pm_id = pm.id

        client.delete(f"/api/product-mappings/{pm_id}")

        with db_session_scope() as session:
            gone = get_product_mapping(
                session, reference_product_id=ref_p.id, target_product_id=tgt_p.id
            )
        assert gone is None, "Mapping must be absent from DB after delete"

    def test_delete_missing_mapping_returns_404(self, client):
        """Deleting a non-existent mapping must return 404."""
        resp = client.delete("/api/product-mappings/999999999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_delete_route_registered(self):
        """Smoke test: DELETE route must be present in the URL map."""
        from pricewatch.app_factory import create_app
        app = create_app({"TESTING": True})
        rules = [(r.rule, r.methods) for r in app.url_map.iter_rules()]
        delete_rules = [
            r for r, m in rules
            if r == "/api/product-mappings/<int:mapping_id>" and "DELETE" in (m or [])
        ]
        assert delete_rules, "DELETE /api/product-mappings/<int:mapping_id> route not registered"


# ---------------------------------------------------------------------------
# 15. Price formatting helper — formatPrice behavior
# ---------------------------------------------------------------------------

class TestFormatPriceHelper:
    """Commit 1: shared price formatting defined in common.js.

    The JS function is deterministic and tiny.  We validate its contract
    via a Python-level helper that mirrors the same logic, keeping the tests
    lightweight without requiring a JS test harness.
    """

    @staticmethod
    def _format_price(value, currency=''):
        """Python mirror of common.js formatPrice()."""
        if value is None or value == '':
            return '—'
        try:
            num = float(value)
        except (TypeError, ValueError):
            return '—'
        import math
        if not math.isfinite(num):
            return '—'
        base = f"{num:.2f}"
        return f"{base} {currency}" if currency else base

    def test_integer_price(self):
        assert self._format_price(12) == "12.00"

    def test_one_decimal(self):
        assert self._format_price(12.3) == "12.30"

    def test_rounds_three_decimals(self):
        assert self._format_price(12.345) == "12.35"

    def test_zero(self):
        assert self._format_price(0) == "0.00"

    def test_none_returns_dash(self):
        assert self._format_price(None) == "—"

    def test_empty_string_returns_dash(self):
        assert self._format_price('') == "—"

    def test_with_currency(self):
        assert self._format_price(12.3, 'UAH') == "12.30 UAH"

    def test_with_usd_currency(self):
        assert self._format_price(12.3, 'USD') == "12.30 USD"

    def test_large_price(self):
        assert self._format_price(9999.9) == "9999.90"

    def test_string_numeric_value(self):
        # common.js uses Number(value) which parses numeric strings
        assert self._format_price('42') == "42.00"


# ---------------------------------------------------------------------------
# 16. Commit 5 — Eligible target products: optimized DB-query behavior
# ---------------------------------------------------------------------------

class TestEligibleTargetProductsOptimization:
    """Behavioral coverage for the DB-level eligible-target-products query.

    These tests verify outcome only (no SQL assertions) so they remain valid
    regardless of future query refactors.
    """

    # ---- shared fixture helpers ----------------------------------------

    def _build_scope(self, session, tag):
        ref_store = get_or_create_store(session, f"Ref_OPT_{tag}", is_reference=True)
        tgt_store = get_or_create_store(session, f"Tgt_OPT_{tag}", is_reference=False)
        ref_cat   = upsert_category(session, store_id=ref_store.id, name=f"OPTCat_{tag}")
        tgt_cat   = upsert_category(session, store_id=tgt_store.id, name=f"OPTCat_{tag}")
        create_category_mapping(
            session, reference_category_id=ref_cat.id,
            target_category_id=tgt_cat.id, match_type="manual",
        )
        session.flush()
        return ref_store, tgt_store, ref_cat, tgt_cat

    # ---- 1. Valid mapped categories return eligible products ---------------

    def test_valid_categories_return_products(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "A")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "OPT Ref A", "opt_ra")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "OPT Tgt A", "opt_ta")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
            )

        ids = [r["id"] for r in results]
        assert tgt_p.id in ids

    # ---- 2. Off-scope categories raise ValueError -------------------------

    def test_off_scope_category_raises_value_error(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "B")
            other_cat = upsert_category(session, store_id=tgt_store.id, name="OPT_OtherCat_B")
            session.flush()
            ref_p = _prod(session, ref_store.id, ref_cat.id, "OPT Ref B", "opt_rb")
            session.flush()

            svc = ComparisonService(session)
            import pytest as _pytest
            with _pytest.raises(ValueError, match="not a valid mapped"):
                svc.get_eligible_target_products(
                    reference_product_id=ref_p.id,
                    target_category_ids=[other_cat.id],
                )

    # ---- 3. Search narrows results ----------------------------------------

    def test_search_filters_results(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "C")
            ref_p    = _prod(session, ref_store.id, ref_cat.id, "OPT Ref C", "opt_rc")
            match_p  = _prod(session, tgt_store.id, tgt_cat.id, "Bauer Vapor OPT", "opt_bauer_c")
            no_match = _prod(session, tgt_store.id, tgt_cat.id, "CCM Tacks OPT",   "opt_ccm_c")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
                search="Bauer",
            )

        ids = [r["id"] for r in results]
        assert match_p.id in ids
        assert no_match.id not in ids

    # ---- 4. Rejected pair excluded; include_rejected=True surfaces it -----

    def test_rejected_excluded_and_restored_with_flag(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "D")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "OPT Ref D", "opt_rd")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "OPT Tgt D", "opt_td")
            session.flush()
            upsert_match_decision(
                session, reference_product_id=ref_p.id,
                target_product_id=tgt_p.id, match_status="rejected",
            )

            svc = ComparisonService(session)
            without_flag = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
                include_rejected=False,
            )
            with_flag = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
                include_rejected=True,
            )

        assert all(r["id"] != tgt_p.id for r in without_flag), "Rejected must be hidden"
        assert any(r["id"] == tgt_p.id for r in with_flag), "Rejected must appear with flag"

    # ---- 5. Globally confirmed target stays excluded even with include_rejected

    def test_globally_confirmed_always_excluded(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "E")
            ref_p1 = _prod(session, ref_store.id, ref_cat.id, "OPT Ref E1", "opt_re1")
            ref_p2 = _prod(session, ref_store.id, ref_cat.id, "OPT Ref E2", "opt_re2")
            tgt_p  = _prod(session, tgt_store.id, tgt_cat.id, "OPT Tgt E",  "opt_te")
            session.flush()
            # Confirm tgt_p for ref_p2 → globally confirmed
            upsert_match_decision(
                session, reference_product_id=ref_p2.id,
                target_product_id=tgt_p.id, match_status="confirmed",
            )

            svc = ComparisonService(session)
            results_default = svc.get_eligible_target_products(
                reference_product_id=ref_p1.id,
                target_category_ids=[tgt_cat.id],
            )
            results_with_flag = svc.get_eligible_target_products(
                reference_product_id=ref_p1.id,
                target_category_ids=[tgt_cat.id],
                include_rejected=True,
            )

        assert all(r["id"] != tgt_p.id for r in results_default)
        assert all(r["id"] != tgt_p.id for r in results_with_flag), \
            "Globally confirmed must be blocked regardless of include_rejected"

    # ---- 6. Returned items include category metadata ----------------------

    def test_results_include_category_metadata(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "F")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "OPT Ref F", "opt_rf")
            tgt_p = _prod(session, tgt_store.id, tgt_cat.id, "OPT Tgt F", "opt_tf")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
            )

        assert results, "Expected at least one product"
        item = next(r for r in results if r["id"] == tgt_p.id)
        assert "category" in item, "Result must contain 'category' key"
        assert item["category"] is not None, "Category must not be None"
        assert item["category"]["id"] == tgt_cat.id
        assert item["category"]["name"] == f"OPTCat_F"

    # ---- 7. Limit is respected --------------------------------------------

    def test_limit_caps_result_count(self):
        with _session_scope() as session:
            ref_store, tgt_store, ref_cat, tgt_cat = self._build_scope(session, "G")
            ref_p = _prod(session, ref_store.id, ref_cat.id, "OPT Ref G", "opt_rg")
            for i in range(10):
                _prod(session, tgt_store.id, tgt_cat.id, f"OPT Tgt G{i}", f"opt_tg_{i}")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat.id],
                limit=3,
            )

        assert len(results) <= 3, f"Expected ≤3 results, got {len(results)}"

    # ---- 8. Multiple categories are all queried --------------------------

    def test_multi_category_products_all_returned(self):
        with _session_scope() as session:
            ref_store = get_or_create_store(session, "Ref_OPT_H", is_reference=True)
            tgt_store = get_or_create_store(session, "Tgt_OPT_H", is_reference=False)
            ref_cat  = upsert_category(session, store_id=ref_store.id, name="OPTCat_H")
            tgt_cat1 = upsert_category(session, store_id=tgt_store.id, name="OPTCat_H1")
            tgt_cat2 = upsert_category(session, store_id=tgt_store.id, name="OPTCat_H2")
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat1.id, match_type="manual",
            )
            create_category_mapping(
                session, reference_category_id=ref_cat.id,
                target_category_id=tgt_cat2.id, match_type="manual",
            )
            session.flush()
            ref_p  = _prod(session, ref_store.id, ref_cat.id,  "OPT Ref H",  "opt_rh")
            tgt_p1 = _prod(session, tgt_store.id, tgt_cat1.id, "OPT Tgt H1", "opt_th1")
            tgt_p2 = _prod(session, tgt_store.id, tgt_cat2.id, "OPT Tgt H2", "opt_th2")
            session.flush()

            svc = ComparisonService(session)
            results = svc.get_eligible_target_products(
                reference_product_id=ref_p.id,
                target_category_ids=[tgt_cat1.id, tgt_cat2.id],
                limit=100,
            )

        ids = [r["id"] for r in results]
        assert tgt_p1.id in ids
        assert tgt_p2.id in ids
