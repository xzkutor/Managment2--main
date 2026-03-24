"""Request DTOs for /api/comparison, /api/comparison/confirm-match, and
/api/comparison/match-decision endpoints."""
from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import Field, field_validator

from pricewatch.schemas.base import PricewatchBaseModel


class ComparisonRequest(PricewatchBaseModel):
    """Request body for POST /api/comparison.

    Business rule: reference_category_id is required.
    Exactly one of {target_category_id, target_category_ids, target_store_id}
    must be supplied — validated downstream in ComparisonService (not here).
    """
    reference_category_id: int = Field(..., gt=0, description="ID of the reference category")
    target_category_id: Optional[int] = Field(None, gt=0)
    target_category_ids: Optional[List[int]] = Field(None, min_length=1)
    target_store_id: Optional[int] = Field(None, gt=0)

    @field_validator("target_category_ids", mode="before")
    @classmethod
    def _coerce_target_ids(cls, v):
        if v is not None:
            return [int(i) for i in v]
        return v


class ConfirmMatchRequest(PricewatchBaseModel):
    """Request body for POST /api/comparison/confirm-match (compatibility shim)."""
    reference_product_id: int = Field(..., gt=0)
    target_product_id: int = Field(..., gt=0)
    match_status: Optional[str] = Field("confirmed", max_length=50)
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    comment: Optional[str] = Field(None, max_length=2000)


class MatchDecisionRequest(PricewatchBaseModel):
    """Request body for POST /api/comparison/match-decision.

    Supports both ``confirmed`` and ``rejected`` statuses.
    The ``rejected`` status durably suppresses the exact pair from future
    comparison runs; the decision can be reversed later by sending
    ``confirmed`` for the same pair.

    ``target_category_ids`` is optional.  When provided for a ``confirmed``
    decision, the server validates that the target product actually belongs
    to one of the supplied categories (scope guard).  Old callers that omit
    the field are still accepted (backward-compatible).
    """
    reference_product_id: int = Field(..., gt=0)
    target_product_id: int = Field(..., gt=0)
    match_status: Literal["confirmed", "rejected"]
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    comment: Optional[str] = Field(None, max_length=2000)
    target_category_ids: Optional[List[int]] = Field(None, min_length=1)

    @field_validator("target_category_ids", mode="before")
    @classmethod
    def _coerce_target_cat_ids(cls, v):
        if v is not None:
            return [int(i) for i in v]
        return v


