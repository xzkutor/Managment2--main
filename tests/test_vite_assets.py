"""tests/test_vite_assets.py — Focused tests for Flask ↔ Vite asset integration.

Covers:
1. Dev mode tags (VITE_USE_DEV_SERVER=True)
2. Production manifest tags (JS + optional CSS)
3. Missing manifest → FileNotFoundError / graceful Markup("")
4. Missing entry in manifest → KeyError with actionable message
5. Jinja global registration via create_app()
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from markupsafe import Markup

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(extra_config: dict | None = None):
    """Create a minimal Flask test app without DB bootstrap."""
    os.environ.setdefault("SCHEDULER_ENABLED", "false")
    from app import create_app
    cfg = {"TESTING": True, "DATABASE_URL": "sqlite:///:memory:"}
    if extra_config:
        cfg.update(extra_config)
    app = create_app(cfg)
    return app


def _minimal_manifest(entry: str, js_file: str, css_files: list[str] | None = None) -> dict:
    """Build a minimal Vite manifest dict for testing."""
    entry_data: dict = {"file": js_file, "isEntry": True}
    if css_files:
        entry_data["css"] = css_files
    return {entry: entry_data}


# ---------------------------------------------------------------------------
# 1. Dev mode tags
# ---------------------------------------------------------------------------

class TestDevModeTags:
    def test_dev_mode_emits_vite_client_script(self):
        app = _make_app({
            "VITE_USE_DEV_SERVER": True,
            "VITE_DEV_SERVER_URL": "http://localhost:5173",
        })
        with app.app_context():
            from pricewatch.web.assets import vite_asset_tags
            html = vite_asset_tags("src/entries/service.ts")

        assert "@vite/client" in html
        assert 'type="module"' in html

    def test_dev_mode_includes_entry_url(self):
        app = _make_app({
            "VITE_USE_DEV_SERVER": True,
            "VITE_DEV_SERVER_URL": "http://localhost:5173",
        })
        with app.app_context():
            from pricewatch.web.assets import vite_asset_tags
            html = vite_asset_tags("src/entries/service.ts")

        assert "src/entries/service.ts" in html
        assert "localhost:5173" in html

    def test_dev_mode_returns_markup_instance(self):
        app = _make_app({
            "VITE_USE_DEV_SERVER": True,
            "VITE_DEV_SERVER_URL": "http://localhost:5173",
        })
        with app.app_context():
            from pricewatch.web.assets import vite_asset_tags
            result = vite_asset_tags("src/entries/index.ts")

        assert isinstance(result, Markup)


# ---------------------------------------------------------------------------
# 2. Production manifest tags
# ---------------------------------------------------------------------------

class TestProductionManifestTags:
    def test_prod_emits_script_tag_for_js_asset(self):
        manifest = _minimal_manifest(
            "src/entries/service.ts",
            "assets/service-AbCdEf.js",
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(manifest, f)
            manifest_path = f.name

        try:
            app = _make_app({
                "VITE_USE_DEV_SERVER": False,
                "VITE_MANIFEST_PATH": manifest_path,
            })
            with app.app_context():
                from pricewatch.web.assets import vite_asset_tags
                html = vite_asset_tags("src/entries/service.ts")

            assert "assets/service-AbCdEf.js" in html
            assert 'type="module"' in html
        finally:
            os.unlink(manifest_path)

    def test_prod_emits_css_link_before_script(self):
        manifest = _minimal_manifest(
            "src/entries/service.ts",
            "assets/service-AbCdEf.js",
            css_files=["assets/service-XyZwVu.css"],
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(manifest, f)
            manifest_path = f.name

        try:
            app = _make_app({
                "VITE_USE_DEV_SERVER": False,
                "VITE_MANIFEST_PATH": manifest_path,
            })
            with app.app_context():
                from pricewatch.web.assets import vite_asset_tags
                html = vite_asset_tags("src/entries/service.ts")

            assert 'rel="stylesheet"' in html
            assert "service-XyZwVu.css" in html
            # CSS link must appear before the script tag
            assert html.index("stylesheet") < html.index("type=\"module\"")
        finally:
            os.unlink(manifest_path)

    def test_prod_tags_returns_markup_instance(self):
        manifest = _minimal_manifest(
            "src/entries/index.ts",
            "assets/index-Abc123.js",
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(manifest, f)
            manifest_path = f.name

        try:
            app = _make_app({
                "VITE_USE_DEV_SERVER": False,
                "VITE_MANIFEST_PATH": manifest_path,
            })
            with app.app_context():
                from pricewatch.web.assets import vite_asset_tags
                result = vite_asset_tags("src/entries/index.ts")
            assert isinstance(result, Markup)
        finally:
            os.unlink(manifest_path)


# ---------------------------------------------------------------------------
# 3. Missing manifest
# ---------------------------------------------------------------------------

class TestMissingManifest:
    def test_missing_manifest_returns_empty_markup(self):
        """When the manifest is absent, prod mode returns empty Markup (no crash)."""
        app = _make_app({
            "VITE_USE_DEV_SERVER": False,
            "VITE_MANIFEST_PATH": "/tmp/this_manifest_does_not_exist_pricewatch.json",
        })
        with app.app_context():
            from pricewatch.web.assets import vite_asset_tags
            result = vite_asset_tags("src/entries/service.ts")

        assert result == Markup("")

    def test_missing_manifest_load_raises_file_not_found(self):
        """_load_manifest_cached raises FileNotFoundError with actionable message."""
        from pricewatch.web.assets import _load_manifest_cached
        # Clear lru_cache to avoid interference between tests
        _load_manifest_cached.cache_clear()
        with pytest.raises(FileNotFoundError, match="Vite manifest not found"):
            _load_manifest_cached("/tmp/nonexistent_pricewatch_manifest.json")
        _load_manifest_cached.cache_clear()


# ---------------------------------------------------------------------------
# 4. Missing entry in manifest
# ---------------------------------------------------------------------------

class TestMissingEntryInManifest:
    def test_unknown_entry_raises_key_error(self):
        manifest = _minimal_manifest(
            "src/entries/service.ts",
            "assets/service-AbCdEf.js",
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(manifest, f)
            manifest_path = f.name

        try:
            app = _make_app({
                "VITE_USE_DEV_SERVER": False,
                "VITE_MANIFEST_PATH": manifest_path,
            })
            with app.app_context():
                from pricewatch.web.assets import vite_asset_tags
                with pytest.raises(KeyError, match="not found in manifest"):
                    vite_asset_tags("src/entries/nonexistent.ts")
        finally:
            os.unlink(manifest_path)

    def test_key_error_message_lists_available_entries(self):
        manifest = _minimal_manifest(
            "src/entries/service.ts",
            "assets/service-AbCdEf.js",
        )
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(manifest, f)
            manifest_path = f.name

        try:
            app = _make_app({
                "VITE_USE_DEV_SERVER": False,
                "VITE_MANIFEST_PATH": manifest_path,
            })
            with app.app_context():
                from pricewatch.web.assets import vite_asset_tags
                with pytest.raises(KeyError) as exc_info:
                    vite_asset_tags("src/entries/nonexistent.ts")
            assert "service.ts" in str(exc_info.value)
        finally:
            os.unlink(manifest_path)


# ---------------------------------------------------------------------------
# 5. Jinja global registration
# ---------------------------------------------------------------------------

class TestJinjaGlobalRegistration:
    def test_vite_asset_tags_is_registered_as_jinja_global(self):
        app = _make_app()
        assert "vite_asset_tags" in app.jinja_env.globals

    def test_jinja_global_is_callable(self):
        app = _make_app()
        fn = app.jinja_env.globals["vite_asset_tags"]
        assert callable(fn)

