"""Unit tests for voiceime.context.window — foreground window detection."""

from unittest.mock import patch

import pytest


def _reset_cache():
    """Reset the window detection cache between tests."""
    import voiceime.context.window as w

    w._cached_info = None
    w._cached_at = 0.0
    w._cache_ttl = 0.2


class TestWindowInfo:
    def test_should_create_window_info_with_app_and_title(self):
        from voiceime.context.window import WindowInfo

        info = WindowInfo(app_name="Code.exe", app_title="app.ts — Meteor")
        assert info.app_name == "Code.exe"
        assert info.app_title == "app.ts — Meteor"

    def test_should_default_to_empty_strings(self):
        from voiceime.context.window import WindowInfo

        info = WindowInfo("", "")
        assert info.app_name == ""
        assert info.app_title == ""


class TestGetForegroundWindow:
    @pytest.fixture(autouse=True)
    def _setup(self):
        _reset_cache()

    def test_should_return_window_info_on_success(self):
        import voiceime.context.window as w

        with patch.object(w, "_query_foreground_window",
                          return_value=w.WindowInfo("Code.exe", "test.py")):
            result = w.get_foreground_window()
            assert result == w.WindowInfo("Code.exe", "test.py")

    def test_should_return_empty_on_api_failure(self):
        import voiceime.context.window as w

        with patch.object(w, "_query_foreground_window",
                          side_effect=OSError("access denied")):
            result = w.get_foreground_window()
            assert result == w.WindowInfo("", "")

    def test_should_use_cache_within_ttl(self):
        import voiceime.context.window as w

        w.set_cache_ttl(500)
        w._cached_info = w.WindowInfo("cached.exe", "cache_title")
        w._cached_at = float("inf")  # never expire
        result = w.get_foreground_window()
        assert result.app_name == "cached.exe"

    def test_should_refresh_when_cache_expired(self):
        import voiceime.context.window as w

        w.set_cache_ttl(0)  # zero TTL = always miss
        with patch.object(w, "_query_foreground_window",
                          side_effect=[w.WindowInfo("app1.exe", "a"),
                                       w.WindowInfo("app2.exe", "b")]):
            r1 = w.get_foreground_window()
            r2 = w.get_foreground_window()
            assert r1.app_name == "app1.exe"
            assert r2.app_name == "app2.exe"

    def test_should_handle_empty_hwnd(self):
        import voiceime.context.window as w

        with patch.object(w._user32, "GetForegroundWindow", return_value=None):
            result = w.get_foreground_window()
            assert result == w.WindowInfo("", "")

    def test_should_extract_exe_name_from_full_path(self):
        import voiceime.context.window as w

        with patch.object(w, "_query_foreground_window",
                          return_value=w.WindowInfo("Code.exe", "main.rs")):
            result = w.get_foreground_window()
            assert result.app_name == "Code.exe"
            assert result.app_title == "main.rs"


class TestSetCacheTTL:
    def test_should_update_cache_ttl(self):
        import voiceime.context.window as w

        w.set_cache_ttl(300)
        assert w._cache_ttl == 0.3

        w.set_cache_ttl(0)
        assert w._cache_ttl == 0.0

        w.set_cache_ttl(200)
        assert w._cache_ttl == 0.2
