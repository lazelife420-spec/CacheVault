"""Repository-native pytest sandbox for CacheVault's default file paths.

CacheVault resolves its storage/settings/receipts/CLI-config paths lazily, at
call time, from ``LOCALAPPDATA`` / ``Path.home()`` (see
``cache_vault.core.settings.default_settings_path``,
``cache_vault.core.storage.default_db_path``,
``cache_vault.core.mobile.receipts.default_receipts_path``,
``cache_vault.cli.get_auth_token_or_pair``, and the same
``os.environ.get("LOCALAPPDATA")`` pattern repeated across
crashlog/drag_export/image_assets/editable_copies/capture_debug/clip_context/
command_center/regex_macros/vault_macros/licensing). Nothing in cache_vault
caches those paths at import time, so redirecting the environment variables
they read is sufficient -- but it has to happen before the *first* test body
runs. An autouse fixture is not early enough to guarantee that in general
(fixtures run after collection; collection-time module-level code in a test
file would slip through), so ``bootstrap()`` is called from the top of
tests/conftest.py, at conftest *import* time, which pytest guarantees runs
before collection begins.

Tests that need their own path (``monkeypatch.setenv("LOCALAPPDATA", ...)``,
``monkeypatch.setattr(Path, "home", ...)``, an explicit ``tmp_path`` arg) are
unaffected: monkeypatch overrides apply on top of these defaults for the
duration of the test and are reverted automatically, same as always.
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

SANDBOX_PREFIX = "cachevault-pytest-sandbox-"

# Grace retry for sandbox cleanup (2026-09-30). Windows shell components can
# hold files written under the sandboxed fake profile (Explorer iconcache /
# thumbcache .db files, created when a test opens a common file dialog) for a
# few seconds after the test process is done with them. The strict 2.0s retry
# ladder in cleanup_if_clean() treats that as a cleanup failure and flips an
# otherwise fully green run to exit 1 (measured: 2119/2119 passed, exit 1,
# locks released seconds after the run). One extra rmtree attempt after this
# grace window converts those transient locks into a clean exit; genuinely
# stuck handles still fail loudly. Zero cost on clean runs -- the grace is
# only entered when the ladder already failed.
GRACE_RETRY_DELAY_S = 10.0

# Populated by bootstrap(); None until then.
SANDBOX_ROOT: Path | None = None
LOCALAPPDATA_DIR: Path | None = None
TEMP_DIR: Path | None = None
USERPROFILE_DIR: Path | None = None

# The real (pre-redirect) values, captured at bootstrap time -- for
# regression tests that need to assert the *real* profile was left alone,
# after os.environ["LOCALAPPDATA"] etc. have already been overwritten.
REAL_LOCALAPPDATA_DIR: Path | None = None
REAL_USERPROFILE_DIR: Path | None = None

_bootstrapped = False
_real_temp_root: Path | None = None


def bootstrap() -> Path:
    """Redirect CacheVault's default file-system paths into a throwaway sandbox.

    Idempotent -- safe to call more than once; only the first call creates a
    sandbox and mutates the environment.
    """
    global SANDBOX_ROOT, LOCALAPPDATA_DIR, TEMP_DIR, USERPROFILE_DIR
    global REAL_LOCALAPPDATA_DIR, REAL_USERPROFILE_DIR
    global _bootstrapped, _real_temp_root
    if _bootstrapped:
        return SANDBOX_ROOT

    real_localappdata = os.environ.get("LOCALAPPDATA")
    real_temp = os.environ.get("TEMP")
    real_tmp = os.environ.get("TMP")
    real_userprofile = os.environ.get("USERPROFILE")
    REAL_LOCALAPPDATA_DIR = Path(real_localappdata) if real_localappdata else None
    REAL_USERPROFILE_DIR = Path(real_userprofile) if real_userprofile else None
    # Captured *before* any env var mutation below, so cleanup can later
    # verify the sandbox really was created under the real OS temp dir --
    # not under the (by-then-redirected) sandbox TEMP -- before deleting it.
    _real_temp_root = Path(tempfile.gettempdir())

    root = Path(tempfile.mkdtemp(prefix=SANDBOX_PREFIX, dir=str(_real_temp_root)))
    localappdata_dir = root / "LocalAppData"
    temp_dir = root / "Temp"
    userprofile_dir = root / "UserProfile"
    for d in (localappdata_dir, temp_dir, userprofile_dir):
        d.mkdir(parents=True, exist_ok=True)

    os.environ["LOCALAPPDATA"] = str(localappdata_dir)
    os.environ["TEMP"] = str(temp_dir)
    os.environ["TMP"] = str(temp_dir)
    # cache_vault.cli.get_auth_token_or_pair() writes ~/.cache_vault_cli.json
    # via Path.home(), independent of LOCALAPPDATA on Windows
    # (os.path.expanduser resolves it from USERPROFILE) -- redirect it too so
    # the CLI auto-pairing path can't touch the real user profile either.
    os.environ["USERPROFILE"] = str(userprofile_dir)

    # Never spin up a real system-tray icon during the test suite. pystray's
    # Windows backend keeps its own non-daemon message-loop thread whose clean
    # shutdown depends on GC/finalizer timing (it can end up blocked deep
    # inside a PIL/tkinter finalizer chain triggered from icon-image
    # regeneration) -- when that happens, threading._shutdown() blocks
    # forever waiting to join it, and the whole test process hangs after
    # pytest has already reported every test as passed. Set before any test
    # imports cache_vault.ui.shell, so every Shell built during the session
    # skips tray-icon creation entirely (see cache_vault/ui/tray.py's
    # TrayController.start()). Existing scripts
    # (scripts/macro_live_smoke.py, scripts/post_rc3_acceptance_gate.py)
    # already opt into this same flag for the same reason; setdefault leaves
    # it overridable for anyone deliberately testing the real tray icon.
    os.environ.setdefault("CACHE_VAULT_DISABLE_TRAY", "1")

    # tempfile caches its resolved temp dir in a module-global the first time
    # gettempdir()/mkstemp() run without an explicit dir=. If anything
    # (pytest itself, a plugin, an earlier import) already triggered that
    # resolution using the *real* TEMP/TMP before this ran, the stale value
    # would survive the os.environ writes above. Clearing it forces
    # re-resolution from the new env vars on next use.
    tempfile.tempdir = None

    SANDBOX_ROOT = root
    LOCALAPPDATA_DIR = localappdata_dir
    TEMP_DIR = temp_dir
    USERPROFILE_DIR = userprofile_dir
    _bootstrapped = True

    diagnostics = (
        f"[cachevault-test-sandbox] session sandbox: {root}\n"
        f"[cachevault-test-sandbox]   LOCALAPPDATA -> {localappdata_dir} (was {real_localappdata})\n"
        f"[cachevault-test-sandbox]   TEMP/TMP     -> {temp_dir} (was {real_temp}/{real_tmp})\n"
        f"[cachevault-test-sandbox]   USERPROFILE  -> {userprofile_dir} (was {real_userprofile})\n"
    )
    (root / "SANDBOX_INFO.txt").write_text(diagnostics, encoding="utf-8")
    # -q suppresses most pytest output but not stderr writes made at conftest
    # import time, so this is visible on every ordinary run without extra
    # flags. pytest_report_header (registered in conftest.py) repeats it in
    # the run's own header for the same reason, belt-and-suspenders.
    sys.stderr.write(diagnostics)
    sys.stderr.flush()

    return root


def cleanup_if_clean(session=None, exitstatus: int = 0) -> bool:
    """Remove the sandbox after a fully green run; keep it otherwise.

    ``exitstatus == 0`` is pytest's own definition of "every collected test
    passed". Anything else (failures, errors, an interrupted run, even "no
    tests collected") leaves the sandbox on disk so a human can inspect what
    a failing/aborted run actually wrote, and prints its path so it isn't
    just silently left behind.

    Lock-flavored deletion failures get one extra attempt after
    GRACE_RETRY_DELAY_S before failure is reported: Windows shell
    components can hold sandbox files a few seconds past the strict retry
    ladder with nothing actually wrong. Genuinely stuck files still fail
    loudly and flip the run's exit status.
    """
    if SANDBOX_ROOT is None:
        return True

    # 1. Close any open Vault and VaultStorage instances globally before cleanup.
    try:
        from cache_vault.core.vault import Vault
        Vault.close_all_open_vaults()
    except Exception:
        pass

    try:
        from cache_vault.core.storage import VaultStorage
        VaultStorage.close_all_open_storages()
    except Exception:
        pass

    if exitstatus == 0:
        # Safety guard: only ever delete a path that (a) we created this
        # session, (b) carries our own sandbox prefix, and (c) is a direct
        # child of the *real* OS temp dir captured before redirection --
        # never something derived from the (now-redirected) sandbox TEMP.
        if not (
            SANDBOX_ROOT.name.startswith(SANDBOX_PREFIX)
            and _real_temp_root is not None
            and SANDBOX_ROOT.parent == _real_temp_root
            and SANDBOX_ROOT.exists()
        ):
            return True

        import gc
        import time

        start_time = time.monotonic()
        max_duration = 2.0  # Strict 2.0s monotonic timing boundary
        delays = (0.0, 0.05, 0.1, 0.2, 0.4, 0.8)
        hit_unrelated_error = False

        for delay in delays:
            if delay:
                if time.monotonic() - start_time >= max_duration:
                    break
                time.sleep(delay)

            gc.collect()

            errors = []

            def _record_error(func, path, exc_info):
                errors.append((func, path, exc_info))

            shutil.rmtree(SANDBOX_ROOT, onerror=_record_error)

            if not SANDBOX_ROOT.exists():
                break

            # Fail fast if errors are not handle-locking / sharing-violation errors
            has_unrelated_error = False
            for func, path, exc_info in errors:
                exc = exc_info[1] if exc_info else None
                if isinstance(exc, FileNotFoundError):
                    continue
                if not isinstance(exc, (PermissionError, OSError)):
                    has_unrelated_error = True
                    break
            if has_unrelated_error:
                hit_unrelated_error = True
                break

        # Grace retry -- see GRACE_RETRY_DELAY_S. Only lock-flavored ladder
        # failures reach this point (unrelated errors broke out with the flag
        # set and earn no grace), and it costs nothing on clean runs.
        if SANDBOX_ROOT.exists() and not hit_unrelated_error:
            time.sleep(GRACE_RETRY_DELAY_S)
            gc.collect()
            shutil.rmtree(SANDBOX_ROOT, onerror=lambda *a: None)

        if SANDBOX_ROOT.exists():
            remaining = [p.relative_to(SANDBOX_ROOT).as_posix() for p in SANDBOX_ROOT.rglob("*") if p.is_file()]
            sys.stderr.write(
                f"[cachevault-test-sandbox] CLEANUP FAILURE: all tests passed, but the sandbox "
                f"could not be fully removed even after the grace retry "
                f"(retained files: {remaining}): {SANDBOX_ROOT}\n"
            )
            sys.stderr.flush()
            if session is not None and hasattr(session, "exitstatus"):
                session.exitstatus = 1
            return False

        return True
    else:
        sys.stderr.write(
            f"[cachevault-test-sandbox] run did not exit 0 (exitstatus={exitstatus}); "
            f"retaining sandbox for inspection: {SANDBOX_ROOT}\n"
        )
        sys.stderr.flush()
        return True
