from __future__ import annotations

from pricewatch.db.repositories import list_runs, get_run


class ScrapeHistoryService:
    def __init__(self, session):
        self.session = session

    def list_runs(self, *, store_id: int | None = None, run_type: str | None = None, status: str | None = None, limit: int | None = None, offset: int | None = None):
        return list_runs(self.session, store_id=store_id, run_type=run_type, status=status, limit=limit, offset=offset)

    def get_run(self, run_id: int):
        run = get_run(self.session, run_id)
        if not run:
            raise ValueError(f"ScrapeRun {run_id} not found")
        return run
from __future__ import annotations

from pricewatch.db.repositories import list_runs, get_run


class ScrapeHistoryService:
    def __init__(self, session):
        self.session = session

    def list_runs(self, *, store_id: int | None = None, run_type: str | None = None, status: str | None = None, limit: int | None = None, offset: int | None = None):
        return list_runs(self.session, store_id=store_id, run_type=run_type, status=status, limit=limit, offset=offset)

    def get_run(self, run_id: int):
        run = get_run(self.session, run_id)
        if not run:
            raise ValueError(f"ScrapeRun {run_id} not found")
        return run
