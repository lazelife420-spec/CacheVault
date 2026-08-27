"""Regression tests for the `--profile-dir <path>` isolated-launch flag
(v0.2.2 profile-isolation patch).

These tests prove:
- --profile-dir is parsed correctly (both `--profile-dir <path>` and
  `--profile-dir=<path>` forms), and fails closed if given with no value.
- Applying --profile-dir actually redirects every profile-scoped default
  path (settings/db/mobile-receipts) to land inside it.
- Verification fails closed (SystemExit, non-zero) if a resolved path would
  land outside the requested profile dir -- proving isolation, not assuming
  it.
- --profile-dir composes safely with --selftest end-to-end via subprocess,
  matching the existing test_selftest_profile_containment.py style, and
  never touches a sentinel standing in for the real profile.

No test in this file launches the normal windowed app (no CacheVaultApp(),
no .mainloop()) -- every check either calls the new helpers directly, or
runs `python app.py --profile-dir <path> --selftest` (headless) via
subprocess, exactly like the existing selftest-containment tests already do.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# --- unit-level: argument parsing -----------------------------------------


def test_resolve_profile_dir_arg_absent_returns_none(monkeypatch):
    import app

    monkeypatch.setattr(sys, "argv", ["app.py"])
    assert app._resolve_profile_dir_arg() is None


def test_resolve_profile_dir_arg_space_form(monkeypatch, tmp_path):
    import app

    monkeypatch.setattr(sys, "argv", ["app.py", "--profile-dir", str(tmp_path)])
    assert app._resolve_profile_dir_arg() == str(tmp_path)


def test_resolve_profile_dir_arg_equals_form(monkeypatch, tmp_path):
    import app

    monkeypatch.setattr(sys, "argv", ["app.py", f"--profile-dir={tmp_path}"])
    assert app._resolve_profile_dir_arg() == str(tmp_path)


def test_resolve_profile_dir_arg_missing_value_fails_closed(monkeypatch):
    import app

    monkeypatch.setattr(sys, "argv", ["app.py", "--profile-dir"])
    with pytest.raises(SystemExit) as exc_info:
        app._resolve_profile_dir_arg()
    assert exc_info.value.code != 0


# --- unit-level: apply + verify -------------------------------------------


def test_apply_profile_dir_redirects_all_profile_scoped_paths(tmp_path, monkeypatch):
    import app
    from cache_vault.core.settings import default_settings_path
    from cache_vault.core.storage import default_db_path
    from cache_vault.core.mobile.receipts import default_receipts_path

    target = tmp_path / "isolated-profile"
    app._apply_and_verify_profile_dir(str(target))

    resolved = target.resolve()
    assert Path(os.environ["LOCALAPPDATA"]).resolve() == resolved
    assert Path(os.environ["USERPROFILE"]).resolve() == resolved
    assert Path(os.environ["TEMP"]).resolve() == resolved
    assert Path(os.environ["TMP"]).resolve() == resolved

    assert default_settings_path().resolve().is_relative_to(resolved)
    assert default_db_path().resolve().is_relative_to(resolved)
    assert default_receipts_path().resolve().is_relative_to(resolved)


def test_apply_profile_dir_creates_directory_if_missing(tmp_path):
    import app

    target = tmp_path / "does-not-exist-yet"
    assert not target.exists()
    app._apply_and_verify_profile_dir(str(target))
    assert target.is_dir()


def test_apply_profile_dir_fails_closed_when_verification_fails(tmp_path, monkeypatch):
    """If a profile-scoped path ever resolved outside the requested
    profile_dir -- e.g. a future code change re-introduces an unscoped
    path -- startup must refuse to continue, not proceed unverified."""
    import app

    def _escaped_path():
        return Path("C:/definitely-not-the-isolated-profile/CacheVault/settings.json")

    monkeypatch.setattr(
        "cache_vault.core.settings.default_settings_path", _escaped_path
    )

    with pytest.raises(SystemExit) as exc_info:
        app._apply_and_verify_profile_dir(str(tmp_path / "isolated-profile"))
    assert exc_info.value.code != 0


# --- subprocess-level: composes safely with --selftest, real sentinel ----


def test_profile_dir_plus_selftest_never_touches_sentinel_real_profile(tmp_path):
    """--profile-dir combined with --selftest must still exit 0 and must
    still never write into a sentinel standing in for the real profile --
    matching the guarantee test_selftest_profile_containment.py already
    proves for --selftest alone."""
    sentinel_dir = tmp_path / "sentinel_profile"
    sentinel_dir.mkdir(parents=True, exist_ok=True)
    (sentinel_dir / "CacheVault").mkdir(parents=True, exist_ok=True)
    (sentinel_dir / "CacheVault" / "sentinel.txt").write_text(
        "REAL_PROFILE_SENTINEL", encoding="utf-8"
    )

    isolated_dir = tmp_path / "explicit-isolated-profile"

    env = os.environ.copy()
    # Ambient LOCALAPPDATA still points at the sentinel (simulating a caller
    # who forgot to override it) -- --profile-dir must win over this.
    env["LOCALAPPDATA"] = str(sentinel_dir)
    env["CACHE_VAULT_DISABLE_TRAY"] = "1"

    res = subprocess.run(
        [sys.executable, "app.py", "--profile-dir", str(isolated_dir), "--selftest"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    assert "selftest OK" in res.stdout
    # sentinel untouched
    cv_items = set(os.listdir(sentinel_dir / "CacheVault"))
    assert cv_items == {"sentinel.txt"}


def test_profile_dir_alone_exits_nonzero_when_value_missing(tmp_path):
    """End-to-end: a bare `--profile-dir` with no path, run through the real
    entry point, must fail closed with a non-zero exit -- never fall through
    to Settings.load()/claim_or_exit()/UI startup."""
    env = os.environ.copy()
    env["CACHE_VAULT_DISABLE_TRAY"] = "1"

    res = subprocess.run(
        [sys.executable, "app.py", "--profile-dir"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0
    assert "requires a path argument" in res.stderr
