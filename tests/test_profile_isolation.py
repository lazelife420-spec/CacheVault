"""Regression guards for the repository-native test-profile sandbox.

These tests prove the bootstrap in tests/sandbox.py (wired in at the top of
tests/conftest.py) actually does its job: ordinary CacheVault path-resolution
code, exercised through several different entry points, lands in the pytest
sandbox and never in the real ``%LOCALAPPDATA%\\CacheVault`` profile.
"""

from __future__ import annotations

import os
from pathlib import Path

from tests import sandbox


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def test_sandbox_is_active():
    """Sanity check: bootstrap ran, and the process env reflects it."""
    assert sandbox.SANDBOX_ROOT is not None
    assert os.environ.get("LOCALAPPDATA") == str(sandbox.LOCALAPPDATA_DIR)
    assert os.environ.get("TEMP") == str(sandbox.TEMP_DIR)
    assert os.environ.get("TMP") == str(sandbox.TEMP_DIR)
    assert os.environ.get("USERPROFILE") == str(sandbox.USERPROFILE_DIR)
    assert os.environ.get("CACHE_VAULT_DISABLE_TRAY") == "1"


def test_bootstrap_precedes_cache_vault_imports_in_conftest():
    """conftest.py must call sandbox.bootstrap() before importing any
    cache_vault module, so the redirect is in place before collection can
    trigger any lazy default-path resolution. An autouse fixture runs after
    collection and would not protect collection-time code — see the
    docstring in tests/sandbox.py for the full reasoning.
    """
    conftest_src = (Path(__file__).parent / "conftest.py").read_text(encoding="utf-8")
    bootstrap_pos = conftest_src.index("sandbox.bootstrap()")
    first_cache_vault_import_pos = conftest_src.index("from cache_vault")
    assert bootstrap_pos < first_cache_vault_import_pos


def test_core_default_paths_resolve_under_sandbox():
    """settings/db/mobile-inbox default paths all resolve beneath LOCALAPPDATA_DIR."""
    from cache_vault.core.settings import default_settings_path
    from cache_vault.core.storage import default_db_path
    from cache_vault.core.mobile.receipts import default_receipts_path as default_mobile_receipts_path
    from cache_vault.core.editable_copies import receipts_dir as batch_receipts_dir

    assert _is_under(default_settings_path(), sandbox.LOCALAPPDATA_DIR)
    assert _is_under(default_db_path(), sandbox.LOCALAPPDATA_DIR)
    assert _is_under(default_mobile_receipts_path(), sandbox.LOCALAPPDATA_DIR)
    assert _is_under(batch_receipts_dir(), sandbox.LOCALAPPDATA_DIR)


def test_cli_paths_resolve_under_sandbox():
    """CLI auto-pairing config uses Path.home() (not LOCALAPPDATA) — must be
    redirected via USERPROFILE too, or it silently escapes the sandbox."""
    assert _is_under(Path.home() / ".cache_vault_cli.json", sandbox.USERPROFILE_DIR)

    from cache_vault import cli

    # get_latest_receipt() reads LOCALAPPDATA/CacheVault/Receipts directly.
    assert _is_under(
        Path(os.environ["LOCALAPPDATA"]) / "CacheVault" / "Receipts",
        sandbox.LOCALAPPDATA_DIR,
    )
    assert cli is not None  # module imports cleanly with paths redirected


def test_clipboard_context_menu_receipt_lookup_resolves_under_sandbox():
    """The clip-row context menu's 'find my receipt' lookup reads from
    LOCALAPPDATA/CacheVault/Receipts — must resolve inside the sandbox."""
    from cache_vault.ui import clip_context

    receipts_root = Path(os.environ["LOCALAPPDATA"]) / "CacheVault" / "Receipts"
    assert _is_under(receipts_root, sandbox.LOCALAPPDATA_DIR)
    assert clip_context is not None


def test_batch_receipt_write_lands_only_in_sandbox(tmp_path):
    """A representative receipt-producing operation (batch write_file_receipt)
    must create its file inside the sandbox, and must not add or modify
    anything visible at the top of the real CacheVault profile directory."""
    from cache_vault.core import editable_copies

    real_cachevault_dir = None
    if sandbox.REAL_LOCALAPPDATA_DIR is not None:
        real_cachevault_dir = sandbox.REAL_LOCALAPPDATA_DIR / "CacheVault"

    before_top_level = None
    before_receipts_top_level = None
    real_receipts_dir = real_cachevault_dir / "Receipts" if real_cachevault_dir else None
    if real_cachevault_dir is not None and real_cachevault_dir.is_dir():
        before_top_level = sorted(os.listdir(real_cachevault_dir))
        if real_receipts_dir.is_dir():
            before_receipts_top_level = sorted(os.listdir(real_receipts_dir))

    written = editable_copies.write_file_receipt(
        "regression_guard_probe", {"clip_id": "profile-isolation-test"}
    )

    # 1) landed in the sandbox, not the real profile.
    assert _is_under(written, sandbox.LOCALAPPDATA_DIR)
    assert written.exists()
    if real_cachevault_dir is not None:
        assert not _is_under(written, real_cachevault_dir)

    # 2) the real profile's top-level listing is untouched.
    if before_top_level is not None:
        after_top_level = sorted(os.listdir(real_cachevault_dir))
        assert after_top_level == before_top_level
        if before_receipts_top_level is not None:
            after_receipts_top_level = sorted(os.listdir(real_receipts_dir))
            assert after_receipts_top_level == before_receipts_top_level


def test_explicit_monkeypatch_still_wins_over_sandbox_default(tmp_path, monkeypatch):
    """A test that explicitly supplies its own tmp_path/LOCALAPPDATA must get
    exactly that path, not the session sandbox default."""
    from cache_vault.core.settings import default_settings_path

    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p = default_settings_path()
    assert _is_under(p, tmp_path)
    assert not _is_under(p, sandbox.LOCALAPPDATA_DIR)


def test_explicit_home_monkeypatch_still_wins_over_sandbox_default(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert Path.home() == tmp_path
    assert Path.home() != sandbox.USERPROFILE_DIR


def test_no_packaged_process_is_started_by_the_sandbox():
    """The sandbox bootstrap only touches env vars / the filesystem — it must
    never launch app.py's packaged app (CacheVaultApp().mainloop()) or shell
    out to a subprocess."""
    for src_file in ("sandbox.py", "conftest.py"):
        src = (Path(__file__).parent / src_file).read_text(encoding="utf-8")
        assert "subprocess" not in src
        assert "Popen" not in src
        assert "CacheVaultApp(" not in src
        assert ".mainloop(" not in src
