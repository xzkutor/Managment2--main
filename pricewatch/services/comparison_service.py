"""DB-first comparison service.

Compares persisted products from a reference category against one or more
mapped target categories.  Mapping-driven: comparison is only allowed for
category pairs that exist in ``category_mappings``.

Result is structured into four flat blocks (not a per-target list):

    confirmed_matches   – stored ProductMapping rows  +  heuristic high-confidence
    candidate_groups    – one entry per reference product with sorted candidates
    reference_only      – reference products with no acceptable match at all
    target_only         – target products not used in confirmed_matches and not
                          present in any candidate list

For each candidate:
    can_accept       – False when the target product is already used in a
                       confirmed mapping (for any reference product).
    disabled_reason  – "already_confirmed_elsewhere" when can_accept is False.

The service is intentionally free of Flask and HTTP concerns.
"""
from __future__ import annotations

from typing import Any

from pricewatch.db.models import Category, Product
from pricewatch.db.repositories.category_repository import (
    get_category,
    list_mapped_target_categories,
)
from pricewatch.db.repositories.product_repository import list_products_by_category
from pricewatch.db.repositories.mapping_repository import (
    list_matches_for_reference_product,
    list_matches_for_target_product,
)
from pricewatch.core.normalize import heuristic_match, HIGH_CONFIDENCE_SCORE


def _serialize_product(prod: Product) -> dict[str, Any]:
    return {
        "id": prod.id,
        "store_id": prod.store_id,
        "category_id": prod.category_id,
        "name": prod.name,
        "normalized_name": prod.normalized_name,
        "name_hash": prod.name_hash,
        "price": prod.price,
        "currency": prod.currency,
        "product_url": prod.product_url,
        "source_url": prod.source_url,
        "is_available": prod.is_available,
        "scraped_at": prod.scraped_at.isoformat() if prod.scraped_at else None,
        "updated_at": prod.updated_at.isoformat() if prod.updated_at else None,
    }


def _serialize_category(cat: Category) -> dict[str, Any]:
    store = getattr(cat, "store", None)
    return {
        "id": cat.id,
        "store_id": cat.store_id,
        "name": cat.name,
        "normalized_name": cat.normalized_name,
        "url": cat.url,
        "store_name": getattr(store, "name", None),
        "is_reference": getattr(store, "is_reference", None),
    }


def _product_to_item(prod: Product) -> dict[str, Any]:
    price_str = f"{prod.price or ''} {prod.currency or ''}".strip()
    return {
        "name": prod.name,
        "price": prod.price,
        "price_raw": price_str,
        "url": prod.product_url,
        "_db_id": prod.id,
    }


class ComparisonService:
    """Compare products from a reference category against mapped target categories.

    New flat response shape::

        {
          "reference_category": {...},
          "target_store": {...} | None,
          "selected_target_categories": [...],
          "summary": {
            "confirmed_matches": int,
            "candidate_groups": int,
            "reference_only": int,
            "target_only": int,
          },
          "confirmed_matches": [...],
          "candidate_groups": [...],
          "reference_only": [...],
          "target_only": [...],
        }
    """

    def __init__(self, session) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def compare(
        self,
        reference_category_id: int,
        *,
        target_category_id: int | None = None,
        target_category_ids: list[int] | None = None,
        target_store_id: int | None = None,
    ) -> dict[str, Any]:
        """Run a mapping-driven comparison.

        Resolution order for target categories:
        1. ``target_category_ids`` (list) – each validated against mappings.
        2. ``target_category_id`` (int) – legacy single-value, converted to list.
        3. Auto-load all mapped target categories, optionally filtered by
           ``target_store_id``.

        Raises ``ValueError`` when:
        - reference category not found or not from a reference store
        - any target_category_id is not mapped to the reference category
        - no mappings exist at all (when ids are omitted)
        """
        ref_cat = self._load_reference_category(reference_category_id)

        # Resolve target category ids
        if target_category_ids is not None:
            ids_to_use: list[int] | None = list(target_category_ids)
        elif target_category_id is not None:
            ids_to_use = [target_category_id]
        else:
            ids_to_use = None

        # Load all mappings (unfiltered) for validation; also filtered for auto-selection
        all_mappings = list_mapped_target_categories(self.session, reference_category_id)
        filtered_mappings = (
            list_mapped_target_categories(
                self.session, reference_category_id, target_store_id=target_store_id
            )
            if target_store_id is not None
            else all_mappings
        )

        if ids_to_use is not None:
            mapped_ids_all = {m.target_category_id for m in all_mappings}
            for tid in ids_to_use:
                # Check existence first (raises "not found")
                self._load_target_category(tid)
                if tid not in mapped_ids_all:
                    raise ValueError(
                        f"Категорія {tid} не знайдена в маппінгах для референсної "
                        f"категорії {reference_category_id}. "
                        "Створіть маппінг на сервісній сторінці."
                    )
            mapping_by_tid = {m.target_category_id: m for m in all_mappings}
            target_pairs: list[tuple[Category, Any]] = []
            for tid in ids_to_use:
                tgt_cat = self._load_target_category(tid)
                target_pairs.append((tgt_cat, mapping_by_tid.get(tid)))
        else:
            if not filtered_mappings:
                raise ValueError(
                    "Для цієї категорії ще не створено меппінг. "
                    "Будь ласка, створіть маппінг на сервісній сторінці або "
                    "запустіть авто-маппінг."
                )
            target_pairs = []
            for mapping in filtered_mappings:
                tgt_cat = getattr(mapping, "target_category", None)
                if tgt_cat is None:
                    tgt_cat = get_category(self.session, mapping.target_category_id)
                if tgt_cat is not None:
                    target_pairs.append((tgt_cat, mapping))

        selected_target_categories = [
            self._serialize_mapping_meta(tgt_cat, m)
            for tgt_cat, m in target_pairs
        ]

        # Infer target_store from target_pairs
        inferred_store = None
        if target_pairs:
            first_tgt_cat = target_pairs[0][0]
            inferred_store = getattr(first_tgt_cat, "store", None)

        result = self._compare_multi(ref_cat, target_pairs)
        result["reference_category"] = _serialize_category(ref_cat)
        result["target_store"] = (
            {
                "id": inferred_store.id,
                "name": inferred_store.name,
                "is_reference": inferred_store.is_reference,
            }
            if inferred_store is not None
            else None
        )
        result["selected_target_categories"] = selected_target_categories
        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_reference_category(self, reference_category_id: int) -> Category:
        ref_cat = get_category(self.session, reference_category_id)
        if ref_cat is None:
            raise ValueError(f"Category {reference_category_id} not found")
        ref_store = getattr(ref_cat, "store", None)
        if not getattr(ref_store, "is_reference", False):
            raise ValueError(
                f"Category {reference_category_id} does not belong to a reference store "
                f"(store '{getattr(ref_store, 'name', ref_cat.store_id)}' is not marked as reference)"
            )
        return ref_cat

    def _load_target_category(self, target_category_id: int) -> Category:
        tgt_cat = get_category(self.session, target_category_id)
        if tgt_cat is None:
            raise ValueError(f"Category {target_category_id} not found")
        tgt_store = getattr(tgt_cat, "store", None)
        if getattr(tgt_store, "is_reference", False):
            raise ValueError(
                f"Category {target_category_id} belongs to a reference store; "
                "target_category_id must belong to a non-reference store"
            )
        return tgt_cat

    @staticmethod
    def _serialize_mapping_meta(tgt_cat: Category, mapping: Any) -> dict[str, Any]:
        tgt_store = getattr(tgt_cat, "store", None)
        return {
            "target_category_id": tgt_cat.id,
            "target_category_name": tgt_cat.name,
            "target_store_id": tgt_cat.store_id,
            "target_store_name": getattr(tgt_store, "name", None),
            "match_type": getattr(mapping, "match_type", None),
            "confidence": getattr(mapping, "confidence", None),
        }

    def _compare_multi(
        self,
        ref_cat: Category,
        target_pairs: list[tuple[Category, Any]],
    ) -> dict[str, Any]:
        """Run comparison against the union of all target category products."""
        ref_products = list_products_by_category(self.session, ref_cat.id)

        # Collect all target products from all selected target categories
        all_tgt_products: list[Product] = []
        tgt_cat_by_product_id: dict[int, Category] = {}
        for tgt_cat, _ in target_pairs:
            tgt_prods = list_products_by_category(self.session, tgt_cat.id)
            for p in tgt_prods:
                all_tgt_products.append(p)
                tgt_cat_by_product_id[p.id] = tgt_cat

        tgt_by_id: dict[int, Product] = {p.id: p for p in all_tgt_products}

        # Set of confirmed target product IDs (any reference) — for can_accept check
        confirmed_tgt_ids_global: set[int] = set()
        for tgt_prod in all_tgt_products:
            existing = list_matches_for_target_product(self.session, tgt_prod.id)
            if any(m.match_status == "confirmed" for m in existing):
                confirmed_tgt_ids_global.add(tgt_prod.id)

        # --- Phase 1: apply stored confirmed ProductMapping rows ---
        confirmed_matches: list[dict[str, Any]] = []
        ref_ids_confirmed: set[int] = set()
        tgt_ids_confirmed: set[int] = set()

        for ref_prod in ref_products:
            saved = list_matches_for_reference_product(self.session, ref_prod.id)
            for pm in saved:
                if pm.match_status != "confirmed":
                    continue
                tgt_id = pm.target_product_id
                if tgt_id not in tgt_by_id:
                    continue
                if tgt_id in tgt_ids_confirmed:
                    continue
                ref_ids_confirmed.add(ref_prod.id)
                tgt_ids_confirmed.add(tgt_id)
                tgt_prod = tgt_by_id[tgt_id]
                tgt_cat = tgt_cat_by_product_id.get(tgt_id)
                confirmed_matches.append({
                    "reference_product": _serialize_product(ref_prod),
                    "target_product": _serialize_product(tgt_prod),
                    "target_category": _serialize_category(tgt_cat) if tgt_cat else None,
                    "score_percent": int(round((pm.confidence or 1.0) * 100)),
                    "score_details": {},
                    "match_source": "confirmed",
                    "is_confirmed": True,
                })

        # --- Phase 2: heuristic matching for remaining products ---
        remaining_ref = [p for p in ref_products if p.id not in ref_ids_confirmed]
        remaining_tgt = [p for p in all_tgt_products if p.id not in tgt_ids_confirmed]

        ref_items = [_product_to_item(p) for p in remaining_ref]
        tgt_items = [_product_to_item(p) for p in remaining_tgt]

        heuristic_results = (
            heuristic_match(ref_items, tgt_items) if (ref_items or tgt_items) else []
        )

        # --- Phase 3: classify heuristic results ---
        candidate_groups: list[dict[str, Any]] = []
        reference_only: list[dict[str, Any]] = []
        tgt_ids_in_candidates: set[int] = set()
        tgt_ids_in_heuristic_confirmed: set[int] = set()

        ref_db_id_to_prod: dict[int, Product] = {p.id: p for p in remaining_ref}
        tgt_db_id_to_prod: dict[int, Product] = {p.id: p for p in remaining_tgt}

        for row in heuristic_results:
            status = row.get("status")
            raw_main = row.get("main")
            raw_other = row.get("other")

            ref_prod = self._find_prod(raw_main, ref_db_id_to_prod) if raw_main else None
            tgt_prod = self._find_prod(raw_other, tgt_db_id_to_prod) if raw_other else None

            if status == "matched":
                score_pct = row.get("score_percent", 0)
                is_high_conf = score_pct >= HIGH_CONFIDENCE_SCORE
                tgt_cat = tgt_cat_by_product_id.get(tgt_prod.id) if tgt_prod else None
                entry = {
                    "reference_product": _serialize_product(ref_prod) if ref_prod else raw_main,
                    "target_product": _serialize_product(tgt_prod) if tgt_prod else raw_other,
                    "target_category": _serialize_category(tgt_cat) if tgt_cat else None,
                    "score_percent": score_pct,
                    "score_details": row.get("score_details", {}),
                    "match_source": "heuristic_high_confidence" if is_high_conf else "heuristic",
                    "is_confirmed": False,
                }
                if is_high_conf:
                    confirmed_matches.append(entry)
                    if tgt_prod:
                        tgt_ids_in_heuristic_confirmed.add(tgt_prod.id)
                else:
                    # Lower-confidence single-candidate group
                    cand_payload = self._build_candidates(
                        [{
                            "score": row.get("score", 0.0),
                            "score_percent": score_pct,
                            "score_details": row.get("score_details", {}),
                            "item": raw_other,
                        }],
                        confirmed_tgt_ids_global,
                        tgt_db_id_to_prod,
                        tgt_cat_by_product_id,
                    )
                    candidate_groups.append({
                        "reference_product": (
                            _serialize_product(ref_prod) if ref_prod else raw_main
                        ),
                        "candidates": cand_payload,
                    })
                    if tgt_prod:
                        tgt_ids_in_candidates.add(tgt_prod.id)

            elif status == "ambiguous" and raw_main is not None:
                raw_cands = row.get("candidates", [])
                cand_payload = self._build_candidates(
                    raw_cands,
                    confirmed_tgt_ids_global,
                    tgt_db_id_to_prod,
                    tgt_cat_by_product_id,
                )
                for c in raw_cands:
                    cand_item = c.get("item") or {}
                    cand_db_id = cand_item.get("_db_id") if isinstance(cand_item, dict) else None
                    if cand_db_id:
                        tgt_ids_in_candidates.add(cand_db_id)
                candidate_groups.append({
                    "reference_product": (
                        _serialize_product(ref_prod) if ref_prod else raw_main
                    ),
                    "candidates": cand_payload,
                })

            elif status == "no_match" and raw_main is not None and raw_other is None:
                reference_only.append({
                    "reference_product": (
                        _serialize_product(ref_prod) if ref_prod else raw_main
                    ),
                })

        # --- Phase 4: build target_only ---
        confirmed_tgt_ids_all = tgt_ids_confirmed | tgt_ids_in_heuristic_confirmed
        target_only: list[dict[str, Any]] = []
        for tgt_prod in all_tgt_products:
            if tgt_prod.id in confirmed_tgt_ids_all:
                continue
            if tgt_prod.id in tgt_ids_in_candidates:
                continue
            tgt_cat = tgt_cat_by_product_id.get(tgt_prod.id)
            target_only.append({
                "target_product": _serialize_product(tgt_prod),
                "target_category": _serialize_category(tgt_cat) if tgt_cat else None,
            })

        return {
            "summary": {
                "confirmed_matches": len(confirmed_matches),
                "candidate_groups": len(candidate_groups),
                "reference_only": len(reference_only),
                "target_only": len(target_only),
            },
            "confirmed_matches": confirmed_matches,
            "candidate_groups": candidate_groups,
            "reference_only": reference_only,
            "target_only": target_only,
        }

    @staticmethod
    def _find_prod(
        raw_item: dict[str, Any] | None,
        id_map: dict[int, Product],
    ) -> Product | None:
        if raw_item is None:
            return None
        db_id = raw_item.get("_db_id") if isinstance(raw_item, dict) else None
        if db_id is not None:
            return id_map.get(db_id)
        return None

    @staticmethod
    def _build_candidates(
        raw_candidates: list[dict[str, Any]],
        confirmed_tgt_ids: set[int],
        tgt_db_id_to_prod: dict[int, Product],
        tgt_cat_by_product_id: dict[int, Category],
    ) -> list[dict[str, Any]]:
        result = []
        for c in raw_candidates:
            cand_item = c.get("item") or {}
            cand_db_id = (
                cand_item.get("_db_id") if isinstance(cand_item, dict) else None
            )
            tgt_prod = tgt_db_id_to_prod.get(cand_db_id) if cand_db_id else None
            tgt_cat = tgt_cat_by_product_id.get(cand_db_id) if cand_db_id else None

            already_confirmed = (cand_db_id in confirmed_tgt_ids) if cand_db_id else False
            result.append({
                "target_product": (
                    _serialize_product(tgt_prod) if tgt_prod else cand_item
                ),
                "target_category": _serialize_category(tgt_cat) if tgt_cat else None,
                "score_percent": c.get("score_percent", 0),
                "score_details": c.get("score_details", {}),
                "match_type": "heuristic",
                "can_accept": not already_confirmed,
                "disabled_reason": (
                    "already_confirmed_elsewhere" if already_confirmed else None
                ),
            })
        return result
