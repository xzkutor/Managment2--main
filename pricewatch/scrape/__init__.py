"""pricewatch.scrape — Scheduler orchestration package.

Provides:
  contracts  — RunnerContext, RunnerResult, BaseRunner
  registry   — runner dispatch registry
  schedule   — schedule timing/computation helpers (wraps croniter)
  scheduler  — due-job detection and run-enqueue logic
  worker     — queued-run claiming and runner dispatch
  runners    — adapter runners over existing sync services
"""

