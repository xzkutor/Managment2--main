"""tests/test_vue_page_shells.py — Smoke tests for Flask page shell rendering.

After Commit 8 cutover all operator-facing routes serve spa.html.

Test coverage:
- Canonical routes (/, /service, /gap, /matches) serve spa.html with the
  correct SPA mount root, main.ts entry tag, and bootstrap payload.
- /app preview alias still serves spa.html (backward compat).
- SPA history-mode catch-all serves spa.html for unknown frontend paths.
- /api/* paths are NOT intercepted by the catch-all:
  - Unknown /api/* paths return 404, not the SPA shell.
- Old per-page entries (src/entries/*.ts) and mount roots are no longer
  present on the canonical routes.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("SCHEDULER_ENABLED", "false")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def shell_client():
    """Minimal Flask test client in Vite dev mode (no built manifest needed)."""
    from app import create_app

    app = create_app({
        "TESTING": True,
        "DATABASE_URL": "sqlite:///:memory:",
        "VITE_USE_DEV_SERVER": True,
        "VITE_DEV_SERVER_URL": "http://localhost:5173",
    })
    with app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get(client, path: str):
    resp = client.get(path)
    assert resp.status_code == 200, f"Expected 200 for {path}, got {resp.status_code}"
    return resp.data.decode("utf-8")


def _assert_spa_shell(html: str, path: str = ""):
    """Assert common SPA shell invariants."""
    assert 'id="app"' in html,                  f"{path}: missing SPA mount root #app"
    assert "src/main.ts" in html,               f"{path}: missing src/main.ts entry"
    assert "__PRICEWATCH_BOOTSTRAP__" in html,  f"{path}: missing bootstrap payload"


# ---------------------------------------------------------------------------
# Canonical routes — all serve spa.html after Commit 8 cutover
# ---------------------------------------------------------------------------

class TestCanonicalRoutesSpaShell:
    """Canonical operator routes now serve the SPA shell, not per-page shells."""

    def test_index_returns_200(self, shell_client):
        assert shell_client.get("/").status_code == 200

    def test_index_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/"), "/")

    def test_service_returns_200(self, shell_client):
        assert shell_client.get("/service").status_code == 200

    def test_service_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/service"), "/service")

    def test_gap_returns_200(self, shell_client):
        assert shell_client.get("/gap").status_code == 200

    def test_gap_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/gap"), "/gap")

    def test_matches_returns_200(self, shell_client):
        assert shell_client.get("/matches").status_code == 200

    def test_matches_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/matches"), "/matches")

    def test_all_canonical_routes_render_identical_shell(self, shell_client):
        """All canonical routes must render the same spa.html content."""
        shells = [_get(shell_client, p) for p in ("/", "/service", "/gap", "/matches")]
        assert all(s == shells[0] for s in shells), \
            "Canonical routes should render identical spa.html content"

    def test_no_per_page_entries_on_index(self, shell_client):
        """Per-page entry tags must no longer appear on canonical routes."""
        html = _get(shell_client, "/")
        assert "src/entries/" not in html

    def test_no_per_page_entries_on_service(self, shell_client):
        html = _get(shell_client, "/service")
        assert "src/entries/" not in html

    def test_no_old_mount_roots_on_index(self, shell_client):
        """Legacy mount roots from per-page shells must not appear."""
        html = _get(shell_client, "/")
        assert 'id="comparison-app"' not in html

    def test_no_old_mount_roots_on_service(self, shell_client):
        html = _get(shell_client, "/service")
        assert 'id="serviceApp"' not in html

    def test_no_inline_onclick_handlers(self, shell_client):
        html = _get(shell_client, "/")
        assert "onclick=" not in html


# ---------------------------------------------------------------------------
# /app preview alias — backward compat (Commit 5)
# ---------------------------------------------------------------------------

class TestSpaPreviewAlias:
    """/app and /app/<subpath> still serve spa.html as a backward-compat alias."""

    def test_app_root_returns_200(self, shell_client):
        assert shell_client.get("/app").status_code == 200

    def test_app_root_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/app"), "/app")

    def test_app_service_subpath_returns_200(self, shell_client):
        assert shell_client.get("/app/service").status_code == 200

    def test_app_gap_subpath_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/app/gap"), "/app/gap")


# ---------------------------------------------------------------------------
# SPA history-mode catch-all
# ---------------------------------------------------------------------------

class TestSpaHistoryFallback:
    """Unrecognised non-API paths should serve the SPA shell for history mode."""

    def test_unknown_path_returns_200(self, shell_client):
        """A path unknown to Flask should still serve spa.html."""
        assert shell_client.get("/some-unknown-frontend-route").status_code == 200

    def test_unknown_path_is_spa_shell(self, shell_client):
        _assert_spa_shell(
            _get(shell_client, "/some-unknown-frontend-route"),
            "/some-unknown-frontend-route",
        )

    def test_nested_unknown_path_returns_200(self, shell_client):
        assert shell_client.get("/settings/account").status_code == 200

    def test_nested_unknown_path_is_spa_shell(self, shell_client):
        _assert_spa_shell(_get(shell_client, "/settings/account"), "/settings/account")


# ---------------------------------------------------------------------------
# /api/* guard — must NOT serve the SPA shell
# ---------------------------------------------------------------------------

class TestApiRoutesNotIntercepted:
    """/api/* paths must not be swallowed by the SPA catch-all."""

    def test_unknown_api_path_returns_404(self, shell_client):
        """/api/nonexistent must return 404, not the SPA shell."""
        resp = shell_client.get("/api/this-does-not-exist")
        assert resp.status_code == 404, (
            f"Expected 404 for unknown /api/ path, got {resp.status_code}"
        )

    def test_unknown_api_path_does_not_serve_spa(self, shell_client):
        resp = shell_client.get("/api/nonexistent-endpoint")
        body = resp.data.decode("utf-8")
        assert 'id="app"' not in body, \
            "SPA shell must not be served for unknown /api/* paths"
        assert "src/main.ts" not in body, \
            "SPA entry tag must not appear in /api/* error response"

    def test_api_stores_returns_json(self, shell_client):
        """/api/stores is a registered API route; must return JSON, not HTML."""
        resp = shell_client.get("/api/stores")
        assert resp.status_code == 200
        assert resp.content_type.startswith("application/json"), \
            f"Expected JSON content-type, got {resp.content_type}"
