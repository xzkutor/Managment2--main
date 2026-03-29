"""pricewatch.web.admin_mapping_routes -- Category mapping routes.

Routes
------
POST   /api/category-mappings/auto-link
GET    /api/category-mappings
POST   /api/category-mappings
PUT    /api/category-mappings/<mapping_id>
DELETE /api/category-mappings/<mapping_id>
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from pricewatch.services.mapping_service import MappingService
from pricewatch.services.category_matching_service import CategoryMatchingService
from pricewatch.schemas.validation import parse_request_body
from pricewatch.schemas.requests.mappings import (
    AutoLinkCategoryMappingsRequest,
    CreateCategoryMappingRequest,
    UpdateCategoryMappingRequest,
)
from pricewatch.web.context import get_db_session
from pricewatch.web.serializers import serialize_mapping, mapping_list_payload

logger = logging.getLogger(__name__)


def register_admin_mapping_routes(bp: Blueprint) -> None:
    """Register category mapping routes on the shared blueprint."""

    @bp.route("/api/category-mappings/auto-link", methods=["POST"])
    def api_auto_link_category_mappings():
        """Auto-create category mappings by exact normalized_name match.

        Response includes both the auto-link summary and the current mapping
        list for the (reference_store_id, target_store_id) pair, so the
        frontend can update its state in a single round-trip.

        Response shape::

            {
              "summary": {"created": N, "skipped_existing": N, "skipped_no_norm": N},
              "created": [...],
              "skipped_existing": [...],
              "mappings": [{...}, ...]
            }
        """
        payload, err = parse_request_body(AutoLinkCategoryMappingsRequest)
        if err:
            return err
        session = get_db_session()()
        try:
            result = CategoryMatchingService.auto_link(
                session,
                reference_store_id=payload.reference_store_id,
                target_store_id=payload.target_store_id,
            )
            session.commit()
            # Fetch the up-to-date mapping list for this store pair and include
            # it in the response so the frontend avoids a second network request.
            service = MappingService(session)
            mappings_payload = mapping_list_payload(
                service,
                payload.reference_store_id,
                payload.target_store_id,
            )
        except ValueError as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        except Exception as exc:
            session.rollback()
            logger.exception("auto_link_category_mappings failed: %s", exc)
            return jsonify({"error": "Internal server error"}), 500
        return jsonify({**result, **mappings_payload})

    @bp.route("/api/category-mappings", methods=["GET"])
    def api_list_category_mappings():
        session = get_db_session()()
        reference_store_id = request.args.get("reference_store_id", type=int)
        target_store_id = request.args.get("target_store_id", type=int)
        service = MappingService(session)
        return jsonify(mapping_list_payload(service, reference_store_id, target_store_id))

    @bp.route("/api/category-mappings", methods=["POST"])
    def api_create_category_mapping():
        payload, err = parse_request_body(CreateCategoryMappingRequest)
        if err:
            return err
        session = get_db_session()()
        service = MappingService(session)
        try:
            mapping = service.create_category_mapping(
                reference_category_id=payload.reference_category_id,
                target_category_id=payload.target_category_id,
                match_type=payload.match_type,
                confidence=payload.confidence,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        reference_store_id = request.args.get("reference_store_id", type=int)
        target_store_id = request.args.get("target_store_id", type=int)
        response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
        response_payload["mapping"] = serialize_mapping(mapping)
        return jsonify(response_payload)

    @bp.route("/api/category-mappings/<int:mapping_id>", methods=["PUT"])
    def api_update_category_mapping(mapping_id: int):
        payload, err = parse_request_body(UpdateCategoryMappingRequest)
        if err:
            return err
        session = get_db_session()()
        service = MappingService(session)
        try:
            mapping = service.update_category_mapping(
                mapping_id,
                match_type=payload.match_type,
                confidence=payload.confidence,
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        reference_store_id = request.args.get("reference_store_id", type=int)
        target_store_id = request.args.get("target_store_id", type=int)
        response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
        response_payload["mapping"] = serialize_mapping(mapping)
        return jsonify(response_payload)

    @bp.route("/api/category-mappings/<int:mapping_id>", methods=["DELETE"])
    def api_delete_category_mapping(mapping_id: int):
        session = get_db_session()()
        service = MappingService(session)
        try:
            service.delete_category_mapping(mapping_id)
            session.commit()
        except Exception as exc:
            session.rollback()
            return jsonify({"error": str(exc)}), 400
        reference_store_id = request.args.get("reference_store_id", type=int)
        target_store_id = request.args.get("target_store_id", type=int)
        response_payload = dict(mapping_list_payload(service, reference_store_id, target_store_id))
        response_payload.update({"deleted": True, "mapping_id": mapping_id})
        return jsonify(response_payload)

