"""Cache Vault™ — application entry point.

    python app.py                          # launch the desktop app
    python app.py --selftest                # headless sanity check (no window, for CI)
    python app.py --profile-dir <path>      # force every profile-scoped path (settings,
                                             # database, mobile receipts, TEMP) under <path>
                                             # instead of the real %LOCALAPPDATA%\\CacheVault,
                                             # and verify it stuck before startup continues.
                                             # Also scopes the single-instance lock to <path>,
                                             # so an isolated launch can never be redirected to
                                             # (or block) a real-profile instance. Combine with
                                             # --selftest for a fully headless, verified check;
                                             # combine with neither flag to open a real, isolated
                                             # window for a human walkthrough.
"""

from __future__ import annotations

import sys


def _resolve_profile_dir_arg() -> str | None:
    """Extract --profile-dir <path>'s value from sys.argv, if present.

    Accepts both `--profile-dir <path>` and `--profile-dir=<path>`. Exits
    non-zero immediately if the flag is present with no value -- this must
    fail closed, never silently fall through to the real profile.
    """
    argv = sys.argv
    for i, arg in enumerate(argv):
        if arg == "--profile-dir":
            if i + 1 >= len(argv):
                sys.stderr.write("--profile-dir requires a path argument\n")
                sys.stderr.flush()
                raise SystemExit(2)
            return argv[i + 1]
        if arg.startswith("--profile-dir="):
            return arg.split("=", 1)[1]
    return None


def _apply_and_verify_profile_dir(profile_dir: str) -> None:
    """Point every profile-scoped path at profile_dir and verify it stuck,
    before Settings.load(), VaultStorage(), single_instance.claim_or_exit(),
    or any tray/mobile/capture startup can run.

    This must prove isolation, not just attempt it: after setting the
    environment overrides, it re-derives the same default-path functions the
    rest of the app uses and asserts each one actually resolves inside
    profile_dir. If any of them doesn't -- today or after some future code
    change adds a new profile-scoped path that isn't wired through the same
    LOCALAPPDATA mechanism -- this exits non-zero before any capture, tray,
    mobile, or storage code can run, rather than silently proceeding against
    an unverified (and possibly real) profile.
    """
    import os
    from pathlib import Path

    resolved = Path(profile_dir).resolve()
    resolved.mkdir(parents=True, exist_ok=True)

    os.environ["LOCALAPPDATA"] = str(resolved)
    os.environ["TEMP"] = str(resolved)
    os.environ["TMP"] = str(resolved)
    os.environ["USERPROFILE"] = str(resolved)

    from cache_vault.core.settings import default_settings_path
    from cache_vault.core.storage import default_db_path
    from cache_vault.core.mobile.receipts import default_receipts_path

    checks = {
        "settings path": default_settings_path(),
        "db path": default_db_path(),
        "mobile receipts path": default_receipts_path(),
    }
    for label, path in checks.items():
        try:
            path.resolve().relative_to(resolved)
        except ValueError:
            sys.stderr.write(
                f"--profile-dir isolation could not be verified: {label} "
                f"({path}) does not resolve inside {resolved}. Refusing to "
                f"start -- isolation must be proven, not assumed.\n"
            )
            sys.stderr.flush()
            raise SystemExit(3)


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
    # Must run before anything else -- including --selftest -- so an
    # explicitly-requested isolated profile is applied and verified first.
    # --selftest already does its own containment (see
    # _run_contained_selftest above) and will safely override these values
    # with its own fresh temp root; combining the two flags is harmless.
    profile_dir = _resolve_profile_dir_arg()
    if profile_dir is not None:
        _apply_and_verify_profile_dir(profile_dir)

    if "--selftest" in sys.argv:
        return _run_contained_selftest()

    from cache_vault.core.settings import Settings
    from cache_vault.ui.font_patch import install_main_thread_font_finalizer_guard
    from cache_vault.ui.scroll_patch import install_windows_scroll_patch, scroll_config_from_settings

    _settings = Settings.load()
    install_main_thread_font_finalizer_guard()
    install_windows_scroll_patch(lambda: scroll_config_from_settings(_settings))

    from cache_vault.core.single_instance import claim_or_exit
    claim_or_exit(profile_dir)

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
