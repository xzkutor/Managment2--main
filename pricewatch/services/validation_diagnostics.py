from __future__ import annotations

from typing import Any, Dict, Optional


def ensure_metadata(metadata: Dict[str, Any], *, skipped_key: str = "skipped_invalid", sample_limit: int = 10) -> None:
    """Ensure metadata contains expected diagnostics keys.

    - skipped_key: name of the skipped count (e.g., skipped_invalid_products)
    - sample_limit: cap for validation_errors_sample
    """
    metadata.setdefault(skipped_key, 0)
    metadata.setdefault("validation_error_counts", {})
    metadata.setdefault("validation_errors_sample", [])
    # store sample_limit if caller wants to introspect (optional)
    metadata.setdefault("_validation_errors_sample_limit", sample_limit)


def record_validation_error(
    metadata: Dict[str, Any],
    reason: str,
    message: str,
    *,
    extra_fields: Optional[Dict[str, Any]] = None,
    skipped_key: str = "skipped_invalid",
    sample_limit: int = 10,
) -> None:
    """Increment counters and append a capped sample entry.

    extra_fields will be merged into the stored sample entry.
    """
    ensure_metadata(metadata, skipped_key=skipped_key, sample_limit=sample_limit)

    # increment skipped counter
    metadata[skipped_key] = metadata.get(skipped_key, 0) + 1

    # increment counts by reason
    counts = metadata.setdefault("validation_error_counts", {})
    counts[reason] = counts.get(reason, 0) + 1

    # append to samples if under limit
    samples = metadata.setdefault("validation_errors_sample", [])
    if len(samples) < sample_limit:
        entry = {"type": reason, "message": message}
        if extra_fields:
            entry.update(extra_fields)
        samples.append(entry)


# optional helper to prepare a structured warning payload for logs/UI
def prepare_warning_payload(reason: str, message: str, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload = {"type": reason, "message": message}
    if extra_fields:
        payload.update(extra_fields)
    return payload

