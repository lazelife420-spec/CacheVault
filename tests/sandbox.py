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


def cleanup_if_clean(exitstatus: int) -> None:
    """Remove the sandbox after a fully green run; keep it otherwise.

    ``exitstatus == 0`` is pytest's own definition of "every collected test
    passed". Anything else (failures, errors, an interrupted run, even "no
    tests collected") leaves the sandbox on disk so a human can inspect what
    a failing/aborted run actually wrote, and prints its path so it isn't
    just silently left behind.
    """
    if SANDBOX_ROOT is None:
        return
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
            return

        # Tests that build a VaultStorage(tmp_path / "vault.db") without an
        # explicit .close() leave a SQLite WAL/SHM handle open until that
        # object is garbage-collected; on Windows that can make its file
        # (and therefore its parent dir) briefly undeletable, so a plain
        # rmtree(ignore_errors=True) can silently leave debris behind even
        # after every test passed. Force GC to release those handles, then
        # give rmtree one real attempt before falling back to a second try.
        import gc
        import time

        # onerror (not onexc): pyproject.toml declares requires-python>=3.10,
        # and onexc only exists from 3.12 on. onerror is deprecated but still
        # functional through 3.13, and all it needs to do here is swallow the
        # per-file error so rmtree keeps going instead of raising.
        for attempt, delay in enumerate((0, 0.25, 0.75)):
            if delay:
                time.sleep(delay)
            gc.collect()
            shutil.rmtree(SANDBOX_ROOT, onerror=lambda fn, p, excinfo: None)
            if not SANDBOX_ROOT.exists():
                break

        if SANDBOX_ROOT.exists():
            # Honest failure, not a silently-swallowed one: cleanup did not
            # fully succeed even though every test passed. Most likely cause
            # is a still-open SQLite WAL/SHM file from a test-owned
            # VaultStorage that was never explicitly closed.
            sys.stderr.write(
                f"[cachevault-test-sandbox] all tests passed, but the sandbox "
                f"could not be fully removed (likely a file still open, e.g. "
                f"an unclosed VaultStorage's SQLite WAL/SHM handle): "
                f"{SANDBOX_ROOT}\n"
            )
            sys.stderr.flush()
    else:
        sys.stderr.write(
            f"[cachevault-test-sandbox] run did not exit 0 (exitstatus={exitstatus}); "
            f"retaining sandbox for inspection: {SANDBOX_ROOT}\n"
        )
        sys.stderr.flush()
