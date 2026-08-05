"""Cache Vault™ — application entry point.

    python app.py            # launch the desktop app
    python app.py --selftest # headless sanity check (no window, for CI)
"""

from __future__ import annotations

import sys


def _selftest() -> int:
    """Exercise the core pipeline without a display — used by CI smoke checks."""
    try:
        from io import BytesIO

        from PIL import Image

        from cache_vault.core.mobile.bridge import MobileBridge
        from cache_vault.core.settings import Settings
        from cache_vault.core.storage import VaultStorage
        from cache_vault.core.vault import Vault

        vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
        vault.settings.block_sensitive_auto_capture = False
        vault.capture("https://example.com", source_app="test")
        vault.capture("git status", source_app="test")
        secret = vault.capture("sk-abc123DEF456ghi789JKL0", source_app="test")
        assert secret is not None and secret.is_sensitive
        assert len(vault.list_clips()) == 3

        buf = BytesIO()
        Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
        png = buf.getvalue()
        img = vault.capture_image(png, width=4, height=4, source_app="test")
        assert img is not None
        assert vault.storage.has_clip_asset(img.id)

        bridge = MobileBridge(vault)
        assert bridge.allowed_routes()  # mobile stack importable in frozen builds

        # Verify the bundled CustomTkinter exposes the private APIs the Windows
        # wheel-scroll patch depends on. This is inspection-only (no Tk root, no
        # patch install), and closes the gap where a packaged EXE could ship an
        # incompatible CustomTkinter that only crashed on the first wheel event.
        from cache_vault.ui.scroll_patch import verify_scroll_patch_compatibility

        verify_scroll_patch_compatibility()

        # Licensing / Ed25519 must work in frozen builds (Founder MVP gate).
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cache_vault import licensing

        Ed25519PrivateKey.generate()  # cryptography backend alive
        missing = licensing.load_license()
        if missing.state == licensing.LicenseState.MISSING_LICENSE:
            pass
        elif missing.state == licensing.LicenseState.FOUNDER_VALID:
            assert licensing.is_feature_enabled("proof_pack_export")
        else:
            raise RuntimeError(f"license smoke failed: {missing.state.value} — {missing.message}")

        vault.clear_sensitive()
        vault.close()
        print("selftest OK — core capture/classify/sensitive/image/mobile pipeline works")
        return 0
    except Exception as exc:
        sys.stderr.write(f"selftest failed: {exc}\n")
        sys.stderr.flush()
        return 1


def _run_contained_selftest() -> int:
    """Run selftest inside an automatically managed, isolated temporary profile root.

    Maintains 100% containment:
    - Never reads from or writes to the real user profile (%LOCALAPPDATA%\\CacheVault).
    - Creates a unique temporary directory for every selftest execution.
    - Sets process-local path overrides and disables tray/external capture.
    - Cleans up the temporary directory in a finally block on success or failure.
    - Reports cleanup failures honestly with a non-zero exit code.
    """
    import os
    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="cachevault-selftest-")
    orig_env = {
        k: os.environ.get(k)
        for k in ("LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE", "CACHE_VAULT_DISABLE_TRAY")
    }

    try:
        os.environ["LOCALAPPDATA"] = temp_dir
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir
        os.environ["USERPROFILE"] = temp_dir
        os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"

        res = _selftest()
    except Exception as exc:
        sys.stderr.write(f"selftest execution error: {exc}\n")
        sys.stderr.flush()
        res = 1
    finally:
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
            except Exception as cleanup_exc:
                sys.stderr.write(f"selftest cleanup failed for '{temp_dir}': {cleanup_exc}\n")
                sys.stderr.flush()
                res = 1
    return res


def main() -> int:
    if "--selftest" in sys.argv:
        return _run_contained_selftest()

    from cache_vault.core.settings import Settings
    from cache_vault.ui.scroll_patch import install_windows_scroll_patch, scroll_config_from_settings

    _settings = Settings.load()
    install_windows_scroll_patch(lambda: scroll_config_from_settings(_settings))

    from cache_vault.core.single_instance import claim_or_exit
    claim_or_exit()

    try:
        import customtkinter as ctk
    except ImportError:
        sys.stderr.write(
            "customtkinter is not installed.\n"
            "Install dependencies first:  pip install -r requirements.txt\n"
        )
        return 1

    from cache_vault.ui.crashlog import install_global_hook
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    # Wrap report_callback_exception to suppress/log benign late Tk callbacks
    _orig_report = CacheVaultApp.report_callback_exception

    def _secured_report(self, exc, val, tb):
        is_tcl_error = False
        if exc is not None:
            if getattr(exc, "__name__", "") == "TclError":
                is_tcl_error = True
        if not is_tcl_error and val is not None:
            if getattr(type(val), "__name__", "") == "TclError":
                is_tcl_error = True

        if is_tcl_error:
            err_text = str(val or "")
            is_benign = (
                "bad window path name" in err_text
                or ("bitmap" in err_text and "not defined" in err_text)
                or "CustomTkinter_icon_Windows.ico" in err_text
            )
            if is_benign:
                try:
                    from cache_vault.ui.crashlog import write_crash
                    err = val if isinstance(val, BaseException) else Exception(val)
                    write_crash("benign Tk callback error (suppressed)", err)
                except Exception:  # noqa: BLE001
                    pass
                return

        _orig_report(self, exc, val, tb)

    CacheVaultApp.report_callback_exception = _secured_report

    install_global_hook()
    apply_app_theme()
    app = CacheVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
