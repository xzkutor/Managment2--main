"""pricewatch.scrape.contracts — Execution contracts for scheduler runners.

Defines:
- RunnerContext  — input provided to every runner
- RunnerResult   — structured output produced by every runner
- BaseRunner     — abstract base that all runner adapters must implement
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RunnerContext:
    """Immutable context passed to a runner on each execution."""

    run_id: int
    job_id: int | None
    runner_type: str
    # Job params JSON as parsed dict (may be empty)
    params: dict[str, Any] = field(default_factory=dict)
    # Optional resume checkpoint from the previous attempt
    checkpoint_in: dict[str, Any] | None = None
    # DB session — provided by worker; runner must NOT commit
    session: Any = None


@dataclass
class RunnerResult:
    """Structured result returned by a runner to the worker.

    Retry semantics (Decision 4 — RFC-008 addendum):
      ``retryable`` signals whether the scheduler MAY create a retry run
      for this failure.  The *worker* only persists this flag — it MUST NOT
      enqueue a retry run itself.  Setting ``retryable=True`` on a successful
      run is valid but has no effect.
    """

    # Terminal status: "success" | "partial" | "failed"
    status: str = "success"
    # Human-readable error description (only if status == "failed")
    error_message: str | None = None
    # Optional checkpoint payload for observability / future resume
    checkpoint_out: dict[str, Any] | None = None
    # Summary stats passed through to ScrapeRun counters
    categories_processed: int = 0
    products_processed: int = 0
    products_created: int = 0
    products_updated: int = 0
    price_changes_detected: int = 0
    # Retry metadata — set by runner; persisted by worker; consumed by scheduler
    # True  = this failure is transient; scheduler may retry
    # False = permanent failure; scheduler MUST NOT retry
    retryable: bool = False


class BaseRunner(ABC):
    """Abstract base that all runner adapters must implement."""

    #: Unique string identifier; must match ScrapeJob.runner_type
    runner_type: str = ""

    @abstractmethod
    def run(self, ctx: RunnerContext) -> RunnerResult:
        """Execute the job described by *ctx* and return a result.

        The runner MUST NOT commit the session.
        """

