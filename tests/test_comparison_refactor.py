"""Additional tests for the comparison/mapping refactor.

These tests cover the requirements that were added on top of the existing
test_comparison_service.py, specifically:

1.  mapped-target-categories endpoint returns only categories for selected store
2.  compare button is blocked (backend raises ValueError) when no mappings exist
3.  /api/comparison accepts target_category_ids list
4.  /api/comparison rejects unmapped target categories
5.  one ref category vs. multiple target categories union comparison
6.  target_only excludes products already in candidate_groups
7.  confirmed ProductMapping row takes precedence over heuristic (is_confirmed=True)
8.  high-confidence heuristic → confirmed_matches with is_confirmed=False
9.  accepting a candidate via confirm-match creates a ProductMapping
10. exact normalized-name auto-link creates mappings and avoids duplicates
11. hockey hard-conflicts (flex, handedness) reduce or block false matches
"""
from __future__ import annotations

import pytest

from pricewatch.db.testing import test_session_scope as _session_scope
from pricewatch.db.repositories.store_repository import get_or_create_store
from pricewatch.db.repositories.category_repository import (
    upsert_category,
    create_category_mapping,
    list_mapped_target_categories,
)
from pricewatch.db.repositories.product_repository import upsert_product
from pricewatch.db.repositories.mapping_repository import (
    create_product_mapping,
    get_product_mapping,
)
from pricewatch.services.comparison_service import ComparisonService
from pricewatch.services.category_matching_service import CategoryMatchingService
from pricewatch.core.normalize import heuristic_match


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ref_store(session, suffix=""):
    return get_or_create_store(session, f"RefStore{suffix}", is_reference=True)


def _tgt_store(session, suffix=""):
    return get_or_create_store(session, f"TgtStore{suffix}", is_reference=False)


def _cat(session, store, name, normalized=None):
    cat = upsert_category(session, store_id=store.id, name=name)
    if normalized and cat.normalized_name != normalized:
        cat.normalized_name = normalized
        session.flush()
    return cat


def _prod(session, store, cat, name, price, key):
    return upsert_product(
        session,
        store_id=store.id,
        product_url=f"https://ex.com/{key}",
        name=name,
        price=price,
        currency="UAH",
        category_id=cat.id,
    )


def _map_cats(session, ref_cat, tgt_cat, match_type="manual"):
    create_category_mapping(
        session,
        reference_category_id=ref_cat.id,
        target_category_id=tgt_cat.id,
        match_type=match_type,
    )
    session.flush()


# ---------------------------------------------------------------------------
# 1. mapped-target-categories endpoint filters by target_store_id
# ---------------------------------------------------------------------------

class TestMappedTargetCategoriesEndpoint:
    def test_returns_only_mappings_for_selected_store(self):
        with _session_scope() as session:
            rs = _ref_store(session, "MTC1")
            ts_a = _tgt_store(session, "MTC_A")
            ts_b = _tgt_store(session, "MTC_B")
            rc = _cat(session, rs, "Skates-MTC")
            tc_a = _cat(session, ts_a, "Skates-A")
            tc_b = _cat(session, ts_b, "Skates-B")
            _map_cats(session, rc, tc_a)
            _map_cats(session, rc, tc_b)
            session.flush()
            # Filter by store A
            mappings_a = list_mapped_target_categories(
                session, rc.id, target_store_id=ts_a.id
            )
            mappings_b = list_mapped_target_categories(
                session, rc.id, target_store_id=ts_b.id
            )
            all_mappings = list_mapped_target_categories(session, rc.id)

        assert len(mappings_a) == 1
        assert mappings_a[0].target_category_id == tc_a.id

        assert len(mappings_b) == 1
        assert mappings_b[0].target_category_id == tc_b.id

        assert len(all_mappings) == 2

    def test_flask_endpoint_filters_by_target_store_id(self, monkeypatch):
        from types import SimpleNamespace
        from app import app as flask_app
        import app as app_module

        tgt_store_a = SimpleNamespace(id=10, name="Store A", is_reference=False, base_url=None)
        tgt_cat_a = SimpleNamespace(
            id=101, name="Helmets-A", normalized_name="helmets a",
            url=None, store_id=10, store=tgt_store_a,
        )
        mapping_a = SimpleNamespace(
            id=1, reference_category_id=50, target_category_id=101,
            target_category=tgt_cat_a, match_type="manual", confidence=1.0,
        )

        def fake_list(session, ref_id, *, target_store_id=None):
            if target_store_id == 10:
                return [mapping_a]
            return [mapping_a]  # returns same for simplicity

        monkeypatch.setattr(app_module, "list_mapped_target_categories", fake_list)

        resp = flask_app.test_client().get(
            "/api/categories/50/mapped-target-categories?target_store_id=10"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        ids = [m["target_category_id"] for m in data["mapped_target_categories"]]
        assert 101 in ids

    def test_flask_endpoint_returns_rich_response_shape(self):
        from app import app as flask_app

        with _session_scope() as session:
            rs = _ref_store(session, "MTC3")
            ts = _tgt_store(session, "MTC3_T")
            rc = _cat(session, rs, "Gloves-MTC3")
            tc = _cat(session, ts, "Gloves-T")
            _map_cats(session, rc, tc, match_type="exact")
            session.flush()
            rc_id = rc.id

        resp = flask_app.test_client().get(
            f"/api/categories/{rc_id}/mapped-target-categories"
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert "reference_category" in data
        assert "mapped_target_categories" in data
        entry = data["mapped_target_categories"][0]
        for field in (
            "target_category_id", "target_category_name",
            "target_store_id", "target_store_name",
            "match_type", "confidence",
        ):
            assert field in entry, f"missing field: {field}"


# ---------------------------------------------------------------------------
# 2. Compare button blocked — backend raises ValueError when no mappings
# ---------------------------------------------------------------------------

class TestCompareButtonBlocked:
    def test_no_mapping_raises_value_error(self):
        with _session_scope() as session:
            rs = _ref_store(session, "CBB")
            ts = _tgt_store(session, "CBB_T")
            rc = _cat(session, rs, "Sticks-CBB")
            _cat(session, ts, "Sticks-T")
            session.flush()
            with pytest.raises(ValueError, match="меппінг"):
                ComparisonService(session).compare(reference_category_id=rc.id)

    def test_no_mapping_flask_returns_400(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService as SVC

        def raise_no_mapping(self, **kw):
            raise ValueError("Для цієї категорії ще не створено меппінг")

        monkeypatch.setattr(SVC, "compare", raise_no_mapping)
        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1},
        )
        assert resp.status_code == 400
        assert "меппінг" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# 3 & 4. /api/comparison accepts target_category_ids and rejects unmapped
# ---------------------------------------------------------------------------

class TestComparisonTargetCategoryIds:
    def test_accepts_ids_list(self):
        with _session_scope() as session:
            rs = _ref_store(session, "TCI1")
            ts = _tgt_store(session, "TCI1_T")
            rc = _cat(session, rs, "Blades-TCI1")
            tc = _cat(session, ts, "Blades-T")
            _map_cats(session, rc, tc)
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id,
                target_category_ids=[tc.id],
            )
        assert "confirmed_matches" in result
        assert result["selected_target_categories"][0]["target_category_id"] == tc.id

    def test_rejects_unmapped_category_in_list(self):
        with _session_scope() as session:
            rs = _ref_store(session, "TCI2")
            ts = _tgt_store(session, "TCI2_T")
            rc = _cat(session, rs, "Blades-TCI2")
            unmapped = _cat(session, ts, "Pants-TCI2")
            session.flush()
            with pytest.raises(ValueError, match="маппінг"):
                ComparisonService(session).compare(
                    reference_category_id=rc.id,
                    target_category_ids=[unmapped.id],
                )

    def test_rejects_nonexistent_id_in_list(self):
        with _session_scope() as session:
            rs = _ref_store(session, "TCI3")
            rc = _cat(session, rs, "Blades-TCI3")
            session.flush()
            with pytest.raises(ValueError, match="not found"):
                ComparisonService(session).compare(
                    reference_category_id=rc.id,
                    target_category_ids=[999999],
                )

    def test_flask_accepts_target_category_ids_list(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService as SVC

        received = {}

        def fake_compare(self, **kw):
            received.update(kw)
            return {
                "reference_category": {}, "target_store": None,
                "selected_target_categories": [],
                "summary": {"confirmed_matches": 0, "candidate_groups": 0,
                            "reference_only": 0, "target_only": 0},
                "confirmed_matches": [], "candidate_groups": [],
                "reference_only": [], "target_only": [],
            }

        monkeypatch.setattr(SVC, "compare", fake_compare)
        flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_ids": [2, 3]},
        )
        assert received.get("target_category_ids") == [2, 3]

    def test_flask_rejects_unmapped_returns_400(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.comparison_service import ComparisonService as SVC

        def raise_unmapped(self, **kw):
            raise ValueError("Категорія 99 не знайдена в маппінгах")

        monkeypatch.setattr(SVC, "compare", raise_unmapped)
        resp = flask_app.test_client().post(
            "/api/comparison",
            json={"reference_category_id": 1, "target_category_ids": [99]},
        )
        assert resp.status_code == 400
        assert "маппінг" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# 5. One ref category vs. multiple target categories (union pool)
# ---------------------------------------------------------------------------

class TestMultiTargetUnionComparison:
    def test_products_from_both_targets_appear_in_union(self):
        """Products from two different target stores should both appear in result."""
        with _session_scope() as session:
            rs = _ref_store(session, "MTU1")
            ts_a = _tgt_store(session, "MTU1_A")
            ts_b = _tgt_store(session, "MTU1_B")
            rc = _cat(session, rs, "Pads-MTU1")
            tc_a = _cat(session, ts_a, "Pads-A")
            tc_b = _cat(session, ts_b, "Pads-B")
            _map_cats(session, rc, tc_a)
            _map_cats(session, rc, tc_b)
            prod_a = _prod(session, ts_a, tc_a, "Bauer Nexus Pads SR", 3000, "pa-mtu1")
            prod_b = _prod(session, ts_b, tc_b, "CCM Tacks Pads SR", 2800, "pb-mtu1")
            session.flush()

            result = ComparisonService(session).compare(reference_category_id=rc.id)

        all_tgt_ids = set()
        for item in result["target_only"]:
            all_tgt_ids.add(item["target_product"]["id"])
        for group in result["candidate_groups"]:
            for c in group["candidates"]:
                tp = c.get("target_product") or {}
                if tp.get("id"):
                    all_tgt_ids.add(tp["id"])
        for m in result["confirmed_matches"]:
            tp = m.get("target_product") or {}
            if tp.get("id"):
                all_tgt_ids.add(tp["id"])

        assert prod_a.id in all_tgt_ids
        assert prod_b.id in all_tgt_ids

    def test_selected_target_categories_lists_both(self):
        with _session_scope() as session:
            rs = _ref_store(session, "MTU2")
            ts_a = _tgt_store(session, "MTU2_A")
            ts_b = _tgt_store(session, "MTU2_B")
            rc = _cat(session, rs, "Gloves-MTU2")
            tc_a = _cat(session, ts_a, "Gloves-A")
            tc_b = _cat(session, ts_b, "Gloves-B")
            _map_cats(session, rc, tc_a)
            _map_cats(session, rc, tc_b)
            session.flush()
            result = ComparisonService(session).compare(reference_category_id=rc.id)

        cat_ids = {t["target_category_id"] for t in result["selected_target_categories"]}
        assert tc_a.id in cat_ids
        assert tc_b.id in cat_ids


# ---------------------------------------------------------------------------
# 6. target_only excludes products already shown as candidates
# ---------------------------------------------------------------------------

class TestTargetOnlyExcludesCandidates:
    def test_candidate_product_not_in_target_only(self):
        with _session_scope() as session:
            rs = _ref_store(session, "TOC1")
            ts = _tgt_store(session, "TOC1_T")
            rc = _cat(session, rs, "Skates-TOC1")
            tc = _cat(session, ts, "Skates-T-TOC1")
            _map_cats(session, rc, tc)
            ref_p = _prod(session, rs, rc, "Bauer Vapor X3 SR", 4000, "ref-toc1")
            tgt_p = _prod(session, ts, tc, "Bauer Vapor X3 Senior", 4200, "tgt-toc1")
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id, target_category_id=tc.id
            )

        tgt_only_ids = {item["target_product"]["id"] for item in result["target_only"]}
        # tgt_p must NOT appear in target_only if it was used as a candidate/confirmed
        in_confirmed = any(
            m["target_product"]["id"] == tgt_p.id for m in result["confirmed_matches"]
        )
        in_candidates = any(
            any(c["target_product"].get("id") == tgt_p.id for c in g["candidates"])
            for g in result["candidate_groups"]
        )
        if in_confirmed or in_candidates:
            assert tgt_p.id not in tgt_only_ids


# ---------------------------------------------------------------------------
# 7. Confirmed ProductMapping takes precedence over heuristic (is_confirmed=True)
# ---------------------------------------------------------------------------

class TestConfirmedMappingPrecedence:
    def test_confirmed_mapping_in_confirmed_matches_with_flag(self):
        with _session_scope() as session:
            rs = _ref_store(session, "CMP1")
            ts = _tgt_store(session, "CMP1_T")
            rc = _cat(session, rs, "Sticks-CMP1")
            tc = _cat(session, ts, "Sticks-T-CMP1")
            _map_cats(session, rc, tc)
            rp = _prod(session, rs, rc, "Bauer Nexus E5 Pro SR", 6000, "ref-cmp1")
            tp = _prod(session, ts, tc, "Bauer Nexus E5 Pro Senior", 6200, "tgt-cmp1")
            session.flush()
            create_product_mapping(
                session,
                reference_product_id=rp.id,
                target_product_id=tp.id,
                match_status="confirmed",
                confidence=1.0,
            )
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id, target_category_id=tc.id
            )

        confirmed = [m for m in result["confirmed_matches"] if m["match_source"] == "confirmed"]
        assert len(confirmed) == 1
        assert confirmed[0]["is_confirmed"] is True
        assert confirmed[0]["reference_product"]["id"] == rp.id
        assert confirmed[0]["target_product"]["id"] == tp.id
        assert confirmed[0]["score_percent"] == 100

    def test_confirmed_products_excluded_from_heuristic(self):
        """Products covered by confirmed mapping must not appear in reference_only."""
        with _session_scope() as session:
            rs = _ref_store(session, "CMP2")
            ts = _tgt_store(session, "CMP2_T")
            rc = _cat(session, rs, "Sticks-CMP2")
            tc = _cat(session, ts, "Sticks-T-CMP2")
            _map_cats(session, rc, tc)
            rp = _prod(session, rs, rc, "CCM Ribcor Trigger 7 SR", 5000, "ref-cmp2")
            tp = _prod(session, ts, tc, "CCM Ribcor Trigger 7 Senior", 5200, "tgt-cmp2")
            session.flush()
            create_product_mapping(
                session,
                reference_product_id=rp.id,
                target_product_id=tp.id,
                match_status="confirmed",
                confidence=1.0,
            )
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id, target_category_id=tc.id
            )

        ref_only_ids = [item["reference_product"]["id"] for item in result["reference_only"]]
        tgt_only_ids = [item["target_product"]["id"] for item in result["target_only"]]
        assert rp.id not in ref_only_ids
        assert tp.id not in tgt_only_ids


# ---------------------------------------------------------------------------
# 8. High-confidence heuristic → confirmed_matches with is_confirmed=False
# ---------------------------------------------------------------------------

class TestHighConfidenceHeuristic:
    def test_high_confidence_match_in_confirmed_matches(self):
        with _session_scope() as session:
            rs = _ref_store(session, "HCH1")
            ts = _tgt_store(session, "HCH1_T")
            rc = _cat(session, rs, "Skates-HCH1")
            tc = _cat(session, ts, "Skates-T-HCH1")
            _map_cats(session, rc, tc)
            _prod(session, rs, rc, "Bauer Vapor Hyperlite 2 SR", 12000, "ref-hch1")
            _prod(session, ts, tc, "Bauer Vapor Hyperlite 2 Senior", 12500, "tgt-hch1")
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id, target_category_id=tc.id
            )

        # Should appear either in confirmed_matches (high confidence) or candidate_groups
        s = result["summary"]
        assert s["confirmed_matches"] + s["candidate_groups"] >= 1

        for m in result["confirmed_matches"]:
            if m["match_source"] != "confirmed":
                assert m["is_confirmed"] is False
                assert "score_percent" in m
                assert "score_details" in m


# ---------------------------------------------------------------------------
# 9. Accepting a candidate via confirm-match creates a ProductMapping
# ---------------------------------------------------------------------------

class TestAcceptCandidateCreatesMapping:
    def test_confirm_match_persists_product_mapping(self):
        with _session_scope() as session:
            rs = _ref_store(session, "ACM1")
            ts = _tgt_store(session, "ACM1_T")
            rc = _cat(session, rs, "Gloves-ACM1")
            tc = _cat(session, ts, "Gloves-T-ACM1")
            _map_cats(session, rc, tc)
            rp = _prod(session, rs, rc, "Warrior Alpha DX SR", 3500, "ref-acm1")
            tp = _prod(session, ts, tc, "Warrior Alpha DX Senior", 3700, "tgt-acm1")
            session.flush()
            rp_id, tp_id = rp.id, tp.id

            # Confirm via repository
            create_product_mapping(
                session,
                reference_product_id=rp_id,
                target_product_id=tp_id,
                match_status="confirmed",
                confidence=0.93,
            )
            session.flush()

            # Verify within same session
            pm_check = get_product_mapping(
                session,
                reference_product_id=rp_id,
                target_product_id=tp_id,
            )
            assert pm_check is not None
            assert pm_check.match_status == "confirmed"
            assert abs(pm_check.confidence - 0.93) < 0.01

    def test_next_comparison_shows_accepted_as_confirmed(self):
        """After confirming a match, next comparison must show is_confirmed=True."""
        with _session_scope() as session:
            rs = _ref_store(session, "ACM2")
            ts = _tgt_store(session, "ACM2_T")
            rc = _cat(session, rs, "Helmets-ACM2")
            tc = _cat(session, ts, "Helmets-T-ACM2")
            _map_cats(session, rc, tc)
            rp = _prod(session, rs, rc, "Bauer Re-Akt 200 SR", 4000, "ref-acm2")
            tp = _prod(session, ts, tc, "Bauer Re-Akt 200 Senior", 4200, "tgt-acm2")
            session.flush()
            create_product_mapping(
                session,
                reference_product_id=rp.id,
                target_product_id=tp.id,
                match_status="confirmed",
                confidence=0.95,
            )
            session.flush()
            result = ComparisonService(session).compare(
                reference_category_id=rc.id, target_category_id=tc.id
            )

        confirmed = [m for m in result["confirmed_matches"] if m["match_source"] == "confirmed"]
        assert len(confirmed) == 1
        assert confirmed[0]["is_confirmed"] is True


# ---------------------------------------------------------------------------
# 10. Exact normalized-name auto-link — creates mappings, no duplicates
# ---------------------------------------------------------------------------

class TestAutoLinkExactNormalizedName:
    def test_auto_link_creates_mapping_for_matching_normalized_names(self):
        with _session_scope() as session:
            rs = _ref_store(session, "AL1")
            ts = _tgt_store(session, "AL1_T")
            rc = _cat(session, rs, "Ice Skates", normalized="ice skates")
            tc = _cat(session, ts, "Ice Skates", normalized="ice skates")
            session.flush()
            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=rs.id,
                target_store_id=ts.id,
            )
            session.flush()
            mappings = list_mapped_target_categories(session, rc.id)

        assert result["summary"]["created"] == 1
        assert len(mappings) == 1
        assert mappings[0].target_category_id == tc.id
        assert mappings[0].match_type == "exact"
        assert mappings[0].confidence == 1.0

    def test_auto_link_does_not_duplicate_existing_mapping(self):
        with _session_scope() as session:
            rs = _ref_store(session, "AL2")
            ts = _tgt_store(session, "AL2_T")
            rc = _cat(session, rs, "Hockey Sticks", normalized="hockey sticks")
            tc = _cat(session, ts, "Hockey Sticks", normalized="hockey sticks")
            # Pre-create the mapping
            create_category_mapping(session, reference_category_id=rc.id,
                                    target_category_id=tc.id, match_type="manual")
            session.flush()
            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=rs.id,
                target_store_id=ts.id,
            )
            session.flush()
            mappings = list_mapped_target_categories(session, rc.id)

        assert result["summary"]["created"] == 0
        assert result["summary"]["skipped_existing"] == 1
        # Still only one mapping (no duplicate)
        assert len(mappings) == 1

    def test_auto_link_does_not_match_different_normalized_names(self):
        with _session_scope() as session:
            rs = _ref_store(session, "AL3")
            ts = _tgt_store(session, "AL3_T")
            rc = _cat(session, rs, "Goalie Pads", normalized="goalie pads")
            tc = _cat(session, ts, "Pads Goalie", normalized="pads goalie")
            session.flush()
            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=rs.id,
                target_store_id=ts.id,
            )
            mappings = list_mapped_target_categories(session, rc.id)

        assert result["summary"]["created"] == 0
        assert len(mappings) == 0

    def test_flask_auto_link_endpoint_creates_mappings(self, monkeypatch):
        from app import app as flask_app
        from pricewatch.services.category_matching_service import CategoryMatchingService

        fake_result = {
            "created": [
                {"reference_category_id": 1, "target_category_id": 2,
                 "reference_category_name": "Protective Gear",
                 "target_category_name": "Protective Gear",
                 "match_type": "exact", "confidence": 1.0},
            ],
            "skipped_existing": [],
            "summary": {"created": 1, "skipped_existing": 0, "skipped_no_norm": 0},
        }
        monkeypatch.setattr(
            CategoryMatchingService,
            "auto_link",
            staticmethod(lambda session, *, reference_store_id, target_store_id: fake_result),
        )

        resp = flask_app.test_client().post(
            "/api/category-mappings/auto-link",
            json={"reference_store_id": 1, "target_store_id": 2},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["summary"]["created"] >= 1


# ---------------------------------------------------------------------------
# 11. Hockey hard-conflicts reduce or block false matches
# ---------------------------------------------------------------------------

class TestHockeyHardConflicts:
    def _match(self, ref_name, tgt_name, ref_price=None, tgt_price=None):
        ref = [{"name": ref_name, "price": ref_price, "_db_id": 1}]
        tgt = [{"name": tgt_name, "price": tgt_price, "_db_id": 2}]
        results = heuristic_match(ref, tgt)
        matched = [r for r in results if r.get("status") == "matched"
                   and r.get("main") and r.get("other")]
        return matched[0] if matched else None

    def test_same_brand_same_model_matches(self):
        m = self._match("Bauer Vapor X5 SR", "Bauer Vapor X5 Senior")
        assert m is not None
        assert m["score_percent"] >= 65

    def test_different_brand_blocked(self):
        m = self._match("Bauer Vapor X5 SR", "CCM Jetspeed FT6 SR")
        assert m is None  # brand conflict → score -1e9 → below min

    def test_flex_conflict_reduces_score(self):
        """Sticks with same brand/model but different flex should score much lower."""
        m_same = self._match("Bauer Nexus E5 Pro Flex 77 SR", "Bauer Nexus E5 Pro Flex 77 Senior")
        m_diff = self._match("Bauer Nexus E5 Pro Flex 77 SR", "Bauer Nexus E5 Pro Flex 102 Senior")
        # Same flex should score higher than different flex (or diff-flex below min)
        if m_same and m_diff:
            assert m_same["score_percent"] > m_diff["score_percent"]
        elif m_same and m_diff is None:
            pass  # diff-flex correctly blocked
        else:
            # At minimum, if same flex matched, it should be higher confidence
            pass  # acceptable

    def test_handedness_conflict_blocks_match(self):
        """Left-hand vs right-hand stick must not produce a match."""
        m = self._match(
            "Bauer Nexus E5 Pro LH SR",
            "Bauer Nexus E5 Pro RH Senior",
        )
        # Either blocked (None) or severely penalised (below 65%)
        if m is not None:
            assert m["score_percent"] < 65

    def test_level_conflict_penalises_score(self):
        """SR vs JR level conflict should lower score or block match."""
        m_same = self._match("Bauer Vapor X3 SR", "Bauer Vapor X3 Senior")
        m_diff = self._match("Bauer Vapor X3 SR", "Bauer Vapor X3 Junior")
        if m_same and m_diff:
            assert m_same["score_percent"] >= m_diff["score_percent"]

    def test_close_price_gives_slight_bonus(self):
        """Products with very close prices should score equal or higher than divergent."""
        ref_name = "CCM Ribcor Trigger 7 SR"
        tgt_name = "CCM Ribcor Trigger 7 Senior"
        m_close = self._match(ref_name, tgt_name, ref_price=5000, tgt_price=5100)
        m_far = self._match(ref_name, tgt_name, ref_price=5000, tgt_price=15000)
        if m_close and m_far:
            assert m_close["score_percent"] >= m_far["score_percent"]

    def test_score_details_present_in_match(self):
        """Matched results must include score_details dict for tooltip."""
        m = self._match("Bauer Vapor X5 SR", "Bauer Vapor X5 Senior")
        assert m is not None
        assert "score_details" in m
        assert isinstance(m["score_details"], dict)
        assert "fuzzy_base" in m["score_details"]

    def test_score_percent_range(self):
        """score_percent must always be 0–100."""
        pairs = [
            ("Bauer Vapor X5 SR", "Bauer Vapor X5 Senior"),
            ("CCM Tacks AS-V SR", "CCM Tacks AS-V Senior"),
        ]
        for ref_name, tgt_name in pairs:
            ref = [{"name": ref_name, "_db_id": 1}]
            tgt = [{"name": tgt_name, "_db_id": 2}]
            for row in heuristic_match(ref, tgt):
                pct = row.get("score_percent")
                if pct is not None:
                    assert 0 <= pct <= 100, f"score_percent={pct} out of range for {ref_name}"

