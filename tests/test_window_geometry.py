"""Work-area clamping + main-window geometry persistence.

Covers the tranche that fixed: hardcoded 1200x760 startup that could exceed
short displays, no geometry persistence across launches, a fixed-size
Settings Hub, and the non-resizable 540x840 Pair Android dialog.

Pure clamp/parse helpers run headlessly against synthetic work rects; the
Tk-gated integration tests construct the real app. Every settings object
used here is bound to ``tmp_path`` (or left without a persist path) so no
test can ever write the developer's real %LOCALAPPDATA% settings.json.
"""

from __future__ import annotations

import json
import sys
import time

import pytest

from cache_vault.ui import window_geometry
from tk_support import probe_tk_ui, _tcl_unavailable  # noqa: PLC2701

OK, REASON = probe_tk_ui()


# ---------------------------------------------------------------------------
# Pure helpers (headless)
# ---------------------------------------------------------------------------


class TestParseFormat:
    def test_parse_valid(self):
        assert window_geometry.parse_geometry("1200x760+82+4") == (1200, 760, 82, 4)
        assert window_geometry.parse_geometry("1000x650+0+0") == (1000, 650, 0, 0)

    def test_parse_accepts_negative_offsets(self):
        # Recorded positions can be negative on monitors left of / above the
        # primary display; parse must keep them (apply-time clamping decides).
        assert window_geometry.parse_geometry("1000x650-500+10") == (1000, 650, -500, 10)

    def test_parse_rejects_garbage(self):
        for bad in ("", None, "garbage", "100x100", "100x100+5", "x100+1+2",
                    "0x100+1+2", "100x0+1+2", "100x100++1+2"):
            assert window_geometry.parse_geometry(bad) is None, bad

    def test_format_roundtrip(self):
        s = window_geometry.format_geometry(1200, 760, 82, 4)
        assert s == "1200x760+82+4"
        assert window_geometry.parse_geometry(s) == (1200, 760, 82, 4)
        neg = window_geometry.format_geometry(1000, 650, -500, 10)
        assert neg == "1000x650-500+10"
        assert window_geometry.parse_geometry(neg) == (1000, 650, -500, 10)


class TestClamp:
    AREA = (0, 0, 1366, 728)  # 1366x768 display minus taskbar

    def test_size_capped_to_work_area(self):
        assert window_geometry.clamp_size(1200, 760, self.AREA, 900, 600) == (1200, 728)

    def test_size_honors_minimum_when_area_smaller(self):
        tiny = (0, 0, 800, 600)
        assert window_geometry.clamp_size(1200, 760, tiny, 900, 600) == (900, 600)

    def test_size_noop_when_fits(self):
        assert window_geometry.clamp_size(1000, 650, self.AREA, 900, 600) == (1000, 650)

    def test_position_pulled_back_inside(self):
        # Off-screen saved position (stale multi-monitor value).
        x, y = window_geometry.clamp_position(50000, 50000, 1000, 650, self.AREA)
        assert x == self.AREA[2] - 1000
        assert y == self.AREA[3] - 650

    def test_position_negative_becomes_origin(self):
        assert window_geometry.clamp_position(-500, -10, 1000, 650, self.AREA) == (0, 0)

    def test_position_pins_oversized_window(self):
        # Window larger than the work area (minsize floor): pin at origin so
        # the title bar stays reachable.
        assert window_geometry.clamp_position(50, 50, 900, 600, (0, 0, 800, 500)) == (0, 0)

    def test_fit_end_to_end(self):
        w, h, x, y = window_geometry.fit_geometry(
            1200, 760, 83, 4, self.AREA, 900, 600
        )
        assert (w, h) == (1200, 728)
        assert (x, y) == (83, 0)


def test_query_work_area_returns_zero_without_display():
    class Dead:
        def winfo_screenwidth(self):
            raise RuntimeError("no display")

        def winfo_screenheight(self):
            raise RuntimeError("no display")

    assert window_geometry.query_work_area(Dead()) == (0, 0, 0, 0)


# ---------------------------------------------------------------------------
# Tk-gated integration
# ---------------------------------------------------------------------------


def _make_settings(tmp_path, **overrides):
    from cache_vault.core.settings import Settings

    settings = Settings()
    for key, value in overrides.items():
        setattr(settings, key, value)
    # Bind persistence to the test's tmp dir — never the real profile.
    settings._persist_path = tmp_path / "settings.json"
    return settings


def _make_app(tmp_path, settings):
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.ui.shell import CacheVaultApp

    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=settings)
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _wait_geometry(app, prefix: str, timeout: float = 3.0) -> str:
    deadline = time.time() + timeout
    geo = app.geometry()
    while time.time() < deadline and not geo.startswith(prefix):
        app.update()
        time.sleep(0.02)
        geo = app.geometry()
    return geo


@pytest.mark.skipif(not OK, reason=REASON)
class TestStartupGeometry:
    def test_default_startup_clamped_to_work_area(self, tmp_path):
        """Fresh profile (no saved geometry): centered default, never larger
        than the work area — the old hardcoded 1200x760 overflowed 768px
        displays once the title bar was added."""
        app = _make_app(tmp_path, _make_settings(tmp_path))
        try:
            app.update()
            area = window_geometry.query_work_area(app)
            assert area != (0, 0, 0, 0)
            geo = window_geometry.parse_geometry(app.geometry())
            assert geo is not None
            w, h, x, y = geo
            ax, ay, aw, ah = area
            assert w <= aw and h <= ah
            assert ax <= x and ay <= y
        finally:
            app.destroy()

    def test_saved_geometry_restored(self, tmp_path):
        settings = _make_settings(tmp_path, window_geometry="1000x650+20+10")
        app = _make_app(tmp_path, settings)
        try:
            area = window_geometry.query_work_area(app)
            exp = window_geometry.fit_geometry(1000, 650, 20, 10, area, 900, 600)
            geo = _wait_geometry(app, f"{exp[0]}x{exp[1]}")
            got = window_geometry.parse_geometry(geo)
            assert got is not None and got[:2] == exp[:2], geo
            # Tk normalizes offsets by the window frame on apply, so the
            # restored position may sit a few px from the requested one —
            # but must stay inside the work area and near-identical.
            got_w, got_h, got_x, got_y = got
            ax, ay, aw, ah = area
            assert ax <= got_x <= ax + aw - got_w
            assert ay <= got_y <= ay + ah - got_h
            assert abs(got_x - exp[2]) <= 60 and abs(got_y - exp[3]) <= 60
        finally:
            app.destroy()

    def test_invalid_saved_geometry_falls_back_to_default(self, tmp_path):
        app = _make_app(tmp_path, _make_settings(tmp_path, window_geometry="garbage"))
        try:
            app.update()
            area = window_geometry.query_work_area(app)
            geo = window_geometry.parse_geometry(app.geometry())
            assert geo is not None
            w, h, x, y = geo
            ax, ay, aw, ah = area
            assert w <= aw and h <= ah and ax <= x and ay <= y
            # Still the (clamped) default size family, not a guess.
            assert w <= 1200 and h <= 760
        finally:
            app.destroy()

    def test_offscreen_saved_geometry_clamped_back(self, tmp_path):
        settings = _make_settings(
            tmp_path, window_geometry="1000x650+50000+50000"
        )
        app = _make_app(tmp_path, settings)
        try:
            app.update()
            area = window_geometry.query_work_area(app)
            geo = window_geometry.parse_geometry(app.geometry())
            assert geo is not None
            w, h, x, y = geo
            ax, ay, aw, ah = area
            assert ax <= x <= ax + aw - w
            assert ay <= y <= ay + ah - h
        finally:
            app.destroy()

    @pytest.mark.skipif(sys.platform != "win32", reason="zoomed state is Windows-only")
    def test_maximized_state_restored(self, tmp_path):
        settings = _make_settings(tmp_path, window_maximized=True)
        app = _make_app(tmp_path, settings)
        try:
            app.update()
            assert app.state() == "zoomed"
        finally:
            app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
class TestGeometryPersistence:
    def test_configure_recorder_persists_geometry(self, tmp_path):
        """A move/resize while viewable records the geometry and the
        debounced save writes the bound settings file."""
        settings = _make_settings(tmp_path)
        app = _make_app(tmp_path, settings)
        try:
            app.update()
            app.geometry("1100x700+40+30")

            def _saved_geometry():
                path = tmp_path / "settings.json"
                if not path.exists():
                    return None
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    return None
                return window_geometry.parse_geometry(data.get("window_geometry"))

            # The debounced save fires multiple times (startup mapping batch,
            # then the requested geometry); wait until the file reflects the
            # requested size, not merely until it exists.
            deadline = time.time() + 5.0
            parsed = None
            while time.time() < deadline:
                app.update()
                parsed = _saved_geometry()
                if parsed is not None and parsed[:2] == (1100, 700):
                    break
                time.sleep(0.05)
            assert parsed is not None and parsed[:2] == (1100, 700), parsed
            data = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
            parsed = window_geometry.parse_geometry(data["window_geometry"])
            w, h, x, y = parsed
            area = window_geometry.query_work_area(app)
            ax, ay, aw, ah = area
            assert ax <= x <= ax + aw - w
            assert ay <= y <= ay + ah - h
            assert data["window_maximized"] is False
        finally:
            app.destroy()

    def test_zoomed_session_keeps_last_normal_geometry(self, tmp_path):
        """Maximizing records the maximized flag but must not overwrite the
        saved normal-state geometry with the huge zoomed dimensions."""
        settings = _make_settings(tmp_path, window_geometry="1000x650+20+10")
        app = _make_app(tmp_path, settings)
        try:
            app.update()
            try:
                app.state("zoomed")
            except Exception:  # noqa: BLE001 - zoomed unsupported off-Windows
                pytest.skip("zoomed state unavailable")
            deadline = time.time() + 3.0
            while time.time() < deadline:
                app.update()
                if settings.window_maximized:
                    break
                time.sleep(0.05)
            assert settings.window_maximized is True
            # Last normal geometry survived the maximize.
            assert window_geometry.parse_geometry(settings.window_geometry) == (
                1000, 650, 20, 10,
            )
        finally:
            app.destroy()

    def test_non_profile_settings_never_saved(self, tmp_path, monkeypatch):
        """A bare Settings() (no _persist_path — the shape test sandboxes
        pass in) must never trigger an implicit write to the real profile."""
        from cache_vault.core.settings import Settings

        monkeypatch.setattr(
            Settings, "save",
            lambda self, path=None: pytest.fail(
                "settings.save() called without a persist path"
            ),
        )
        from cache_vault.core.settings import Settings as _S
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.vault import Vault
        from cache_vault.ui.shell import CacheVaultApp

        vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=_S())
        try:
            app = CacheVaultApp(vault=vault)
        except Exception as exc:  # noqa: BLE001
            if _tcl_unavailable(exc):
                pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
            raise
        try:
            app.update()
            app.geometry("1100x700+40+30")
            deadline = time.time() + 0.9
            while time.time() < deadline:
                app.update()
                time.sleep(0.05)
            # Reaching here without pytest.fail means no implicit save ran.
        finally:
            app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
class TestDialogClamps:
    def test_settings_hub_clamped_to_work_area(self, tmp_path, monkeypatch):
        import customtkinter as ctk

        from cache_vault.modules.registry import build_default_registry
        from cache_vault.ui.settings_hub import SettingsHub

        monkeypatch.setattr(
            window_geometry, "query_work_area", lambda widget: (0, 0, 800, 600)
        )
        monkeypatch.setattr(window_geometry, "window_scaling", lambda widget: 1.0)
        root = ctk.CTk()
        root.withdraw()
        try:
            hub = SettingsHub(
                root, _make_settings(tmp_path), build_default_registry(),
                on_save=lambda _s: None,
            )
            try:
                assert hub._open_size == (800, 600)
                hub.present()
                deadline = time.time() + 3.0
                geo = hub.geometry()
                while time.time() < deadline and not geo.startswith("800x600"):
                    hub.update()
                    time.sleep(0.02)
                    geo = hub.geometry()
                assert geo.startswith("800x600"), geo
            finally:
                hub.destroy()
        finally:
            root.destroy()

    def test_settings_hub_unchanged_when_it_fits(self, tmp_path, monkeypatch):
        import customtkinter as ctk

        from cache_vault.modules.registry import build_default_registry
        from cache_vault.ui.settings_hub import SettingsHub

        monkeypatch.setattr(
            window_geometry, "query_work_area", lambda widget: (0, 0, 1920, 1030)
        )
        monkeypatch.setattr(window_geometry, "window_scaling", lambda widget: 1.0)
        root = ctk.CTk()
        root.withdraw()
        try:
            hub = SettingsHub(
                root, _make_settings(tmp_path), build_default_registry(),
                on_save=lambda _s: None,
            )
            try:
                assert hub._open_size == (900, 700)
            finally:
                hub.destroy()
        finally:
            root.destroy()

    def test_pair_android_dialog_clamped_and_resizable(
        self, tmp_path, monkeypatch
    ):
        import customtkinter as ctk

        from cache_vault.ui.mobile_dialogs import PairAndroidDialog

        monkeypatch.setattr(
            window_geometry, "query_work_area", lambda widget: (0, 0, 700, 600)
        )
        real_scaling_fn = window_geometry.window_scaling
        monkeypatch.setattr(window_geometry, "window_scaling", lambda widget: 1.0)
        root = ctk.CTk()
        root.withdraw()
        try:
            dlg = PairAndroidDialog(
                root, on_pair=lambda d, n: (d, "tok"), port=8742
            )
            try:
                # 540x840 design size capped into the 700x600 work area.
                deadline = time.time() + 3.0
                geo = dlg.geometry()
                while time.time() < deadline and not geo.startswith("540x600"):
                    dlg.update()
                    time.sleep(0.02)
                    geo = dlg.geometry()
                assert geo.startswith("540x600"), geo
                # CTk overrides minsize() as setter-only; read the raw Tk
                # value and account for the real window-scaling factor.
                scaling = real_scaling_fn(dlg)
                assert dlg.wm_minsize() == (
                    round(460 * scaling), round(420 * scaling),
                )
                assert dlg.resizable() == (True, True)
            finally:
                dlg.destroy()
        finally:
            root.destroy()
