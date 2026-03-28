"""tests/test_vue_page_shells.py — Smoke tests for Vue-backed Flask page shells.

Verifies the contract between Jinja templates and Vue entry points:
- each page shell exposes the correct Vue mount root ID;
- each page shell includes the Vite entry tag for the expected entry file;
- /service exposes the SERVICE_CONFIG bootstrap object.

These are shell-contract tests, not full browser tests.
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
    """Minimal Flask test client configured for asset-tag rendering in dev mode.

    Using VITE_USE_DEV_SERVER=True ensures vite_asset_tags() emits deterministic
    tags containing the entry name — no real Vite process or built manifest needed.
    """
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


# ---------------------------------------------------------------------------
# GET / — comparison page
# ---------------------------------------------------------------------------

class TestComparisonPageShell:
    def test_mount_root_present(self, shell_client):
        html = _get(shell_client, "/")
        assert 'id="comparison-app"' in html

    def test_vite_entry_tag_present(self, shell_client):
        html = _get(shell_client, "/")
        assert "src/entries/index.ts" in html

    def test_no_legacy_index_js(self, shell_client):
        html = _get(shell_client, "/")
        assert "static/js/index.js" not in html

    def test_no_common_js(self, shell_client):
        html = _get(shell_client, "/")
        assert "common.js" not in html

    def test_no_inline_onclick_handlers(self, shell_client):
        html = _get(shell_client, "/")
        assert "onclick=" not in html


# ---------------------------------------------------------------------------
# GET /service — service console
# ---------------------------------------------------------------------------

class TestServicePageShell:
    def test_mount_root_present(self, shell_client):
        html = _get(shell_client, "/service")
        assert 'id="serviceApp"' in html

    def test_vite_entry_tag_present(self, shell_client):
        html = _get(shell_client, "/service")
        assert "src/entries/service.ts" in html

    def test_service_config_bootstrap_object_present(self, shell_client):
        """SERVICE_CONFIG must be injected by Flask so Vue composables can read it."""
        html = _get(shell_client, "/service")
        assert "SERVICE_CONFIG" in html

    def test_no_common_js(self, shell_client):
        html = _get(shell_client, "/service")
        assert "common.js" not in html

    def test_no_inline_onclick_handlers(self, shell_client):
        html = _get(shell_client, "/service")
        assert "onclick=" not in html


# ---------------------------------------------------------------------------
# GET /gap — gap review
# ---------------------------------------------------------------------------

class TestGapPageShell:
    def test_mount_root_present(self, shell_client):
        html = _get(shell_client, "/gap")
        assert 'id="gap-app"' in html

    def test_vite_entry_tag_present(self, shell_client):
        html = _get(shell_client, "/gap")
        assert "src/entries/gap.ts" in html

    def test_no_legacy_gap_js(self, shell_client):
        html = _get(shell_client, "/gap")
        assert "static/js/gap.js" not in html

    def test_no_common_js(self, shell_client):
        html = _get(shell_client, "/gap")
        assert "common.js" not in html

    def test_no_inline_onclick_handlers(self, shell_client):
        html = _get(shell_client, "/gap")
        assert "onclick=" not in html


# ---------------------------------------------------------------------------
# GET /matches — confirmed matches
# ---------------------------------------------------------------------------

class TestMatchesPageShell:
    def test_mount_root_present(self, shell_client):
        html = _get(shell_client, "/matches")
        assert 'id="matches-app"' in html

    def test_vite_entry_tag_present(self, shell_client):
        html = _get(shell_client, "/matches")
        assert "src/entries/matches.ts" in html

    def test_no_common_js(self, shell_client):
        html = _get(shell_client, "/matches")
        assert "common.js" not in html

    def test_no_inline_onclick_handlers(self, shell_client):
        html = _get(shell_client, "/matches")
        assert "onclick=" not in html

