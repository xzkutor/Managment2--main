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
        assert b"matches" in resp.data.lower() or "підтвердж".encode() in resp.data

    def test_matches_page_contains_table(self, client):
        resp = client.get("/matches")
        assert b"matchesTable" in resp.data or b"product-mappings" in resp.data


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

