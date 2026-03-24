"""pricewatch.web.admin_comparison_gap_routes -- Comparison and gap routes.

Routes
------
POST /api/comparison
POST /api/comparison/match-decision   (new — generic confirmed/rejected decision)
POST /api/comparison/confirm-match    (compatibility shim → match-decision confirmed)
POST /api/gap
POST /api/gap/status
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify

from pricewatch.db.repositories.mapping_repository import upsert_match_decision
from pricewatch.services.comparison_service import ComparisonService
from pricewatch.services.gap_service import GapService
from pricewatch.schemas.validation import parse_request_body
from pricewatch.schemas.requests.comparison import (
    ComparisonRequest,
    ConfirmMatchRequest,
    MatchDecisionRequest,
)
from pricewatch.schemas.requests.gap import GapRequest, GapStatusRequest
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import serialize_product_mapping

logger = logging.getLogger(__name__)


def register_admin_comparison_gap_routes(bp: Blueprint) -> None:
    """Register comparison and gap routes on the shared blueprint."""

    @bp.route("/api/comparison/match-decision", methods=["POST"])
    def api_comparison_match_decision():
        """Persist an explicit match decision (confirmed or rejected) for an exact pair."""
        payload, err = parse_request_body(MatchDecisionRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            pm = upsert_match_decision(
                session,
                reference_product_id=payload.reference_product_id,
                target_product_id=payload.target_product_id,
                match_status=payload.match_status,
                confidence=payload.confidence,
                comment=payload.comment,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("match-decision failed: %s", exc)
            return jsonify({"error": str(exc)}), 400
        return jsonify({"product_mapping": serialize_product_mapping(pm)})

    @bp.route("/api/comparison/confirm-match", methods=["POST"])
    def api_comparison_confirm_match():
        """Compatibility shim: persist a confirmed product match.

        Internally delegates to the same upsert_match_decision path
        with match_status="confirmed".  New callers should prefer
        POST /api/comparison/match-decision.
        """
        payload, err = parse_request_body(ConfirmMatchRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            pm = upsert_match_decision(
                session,
                reference_product_id=payload.reference_product_id,
                target_product_id=payload.target_product_id,
                match_status=payload.match_status or "confirmed",
                confidence=payload.confidence,
                comment=payload.comment,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.exception("confirm-match failed: %s", exc)
            return jsonify({"error": str(exc)}), 400
        return jsonify({"product_mapping": serialize_product_mapping(pm)})

    @bp.route("/api/comparison", methods=["POST"])
    def api_comparison():
        """Compare products from a reference category against mapped target categories."""
        payload, err = parse_request_body(ComparisonRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            svc_kwargs: dict = {"reference_category_id": payload.reference_category_id}
            if payload.target_category_ids is not None:
                svc_kwargs["target_category_ids"] = payload.target_category_ids
            elif payload.target_category_id is not None:
                svc_kwargs["target_category_id"] = payload.target_category_id
            if payload.target_store_id is not None:
                svc_kwargs["target_store_id"] = payload.target_store_id
            result = ComparisonService(session).compare(**svc_kwargs)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            logger.exception("api_comparison failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify(result)

    @bp.route("/api/gap", methods=["POST"])
    def api_gap():
        """Return grouped target-only (gap) items for a reference category + target categories."""
        payload, err = parse_request_body(GapRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            result = GapService(session).build_gap_view(
                target_store_id=payload.target_store_id,
                reference_category_id=payload.reference_category_id,
                target_category_ids=payload.target_category_ids,
                search=payload.search,
                only_available=payload.only_available,
                statuses=payload.statuses,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            logger.exception("api_gap failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify(result)

    @bp.route("/api/gap/status", methods=["POST"])
    def api_gap_status():
        """Persist a gap item review status (in_progress or done)."""
        payload, err = parse_request_body(GapStatusRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            result = GapService(session).set_gap_item_status(
                reference_category_id=payload.reference_category_id,
                target_product_id=payload.target_product_id,
                status=payload.status,
            )
            session.commit()
        except ValueError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            session.rollback()
            logger.exception("api_gap_status failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify({"success": True, "item": result})

