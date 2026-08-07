"""CACHEVAULT ALL CLIPS SEARCH DISCOVERABILITY — isolated QA visual walkthrough.

Launches the real CacheVaultApp from this worktree against a throwaway,
self-contained QA profile (LOCALAPPDATA is redirected to a temp dir so the
user's real profile is never touched) and captures four screenshots of the
All Clips search control:

  1. All Clips before focusing search
  2. search field focused (Proof Teal outline)
  3. typed query with filtered results
  4. cleared query restoring all results

The app is seeded with deterministic QA clips only; capture is paused so the
live OS clipboard is never read. No network, no user profile, no packaging.

Run:
    python scripts/qa_search_discoverability_visual.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# --- Isolate the profile BEFORE importing cache_vault modules that read it. -
_QA_ROOT = Path(tempfile.mkdtemp(prefix="cachevault-qa-search-"))
os.environ["LOCALAPPDATA"] = str(_QA_ROOT / "LocalAppData")
os.environ["TEMP"] = str(_QA_ROOT / "Temp")
os.environ["TMP"] = str(_QA_ROOT / "Temp")
os.environ["USERPROFILE"] = str(_QA_ROOT / "UserProfile")
(_QA_ROOT / "Temp").mkdir(parents=True, exist_ok=True)

# Make the worktree source importable when run as a script from the worktree.
_WORKTREE = Path(__file__).resolve().parents[1]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

import customtkinter as ctk  # noqa: E402

from cache_vault.core.settings import Settings  # noqa: E402
from cache_vault.core.storage import FILTER_ALL, VaultStorage  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402
from cache_vault.ui.shell import CacheVaultApp  # noqa: E402
from cache_vault.ui.theme import apply_app_theme  # noqa: E402
from tests.tk_support import wait_for_refresh  # noqa: E402

try:
    from PIL import ImageGrab
except ImportError:  # pragma: no cover
    ImageGrab = None

OUT = _WORKTREE / "qa_search_screenshots"
OUT.mkdir(exist_ok=True)


def _settle(app, expected_visible=None):
    app._do_refresh_sync()
    if expected_visible is None:
        wait_for_refresh(app)
    else:
        wait_for_refresh(
            app,
            ui_settled=lambda: len(getattr(app, "_visible_clip_ids", [])) == expected_visible,
            ui_description=f"visible clip count == {expected_visible}",
        )
    for _ in range(5):
        app.update_idletasks()
        app.update()


def _shot(app, name: str) -> None:
    app.update_idletasks()
    app.update()
    if ImageGrab is None:
        print(f"[skip] PIL.ImageGrab unavailable — no screenshot for {name}")
        return
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    path = OUT / name
    img.save(path)
    print(f"[shot] {path}")


def main() -> int:
    apply_app_theme()
    # capture_paused: never read the live OS clipboard.
    # first_use_guide_dismissed: skip the onboarding overlay so the All Clips
    # search control is unobstructed in the walkthrough.
    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    storage = VaultStorage(_QA_ROOT / "vault.db")
    vault = Vault(storage=storage, settings=settings)

    seeds = [
        ("Quarterly report draft — Q3 figures", "Word.exe"),
        ("https://github.com/theprooffoundry/cachevault", "chrome.exe"),
        ("def search_clips(query): return vault.list_clips(query)", "cursor.exe"),
        ("git push origin local/cachevault-search-discoverability-20260807", "WindowsTerminal.exe"),
        ("boilerplate marketing copy for the landing page hero", "Word.exe"),
        ("ssh -i ~/.ssh/id_ed25519 deploy@cachevault.example", "WindowsTerminal.exe"),
        ("Quarterly report draft — Q4 outlook notes", "Word.exe"),
    ]
    for content, src in seeds:
        vault.capture(content, source_app=src, force=True)

    app = CacheVaultApp(vault=vault)
    app.geometry("1200x820+80+60")
    app.deiconify()
    app.update_idletasks()
    app.update()

    total = len(seeds)

    # Land on All Clips so the search control is visible.
    app._navigate_screen(FILTER_ALL)
    _settle(app, expected_visible=total)

    # 1. All Clips before focusing search.
    _shot(app, "01_all_clips_search_unfocused.png")

    # 2. Search field focused (Proof Teal outline).
    app._clips_search.focus_set()
    app.update()
    _shot(app, "02_search_focused.png")

    # 3. Typed query with filtered results (two "Quarterly report" clips).
    app._clips_search.focus_set()
    app._search_var.set("Quarterly report")
    _settle(app, expected_visible=2)
    _shot(app, "03_search_filtered.png")

    # 4. Cleared query restoring all results.
    app._clips_search.focus_set()
    app._search_var.set("")
    _settle(app, expected_visible=total)
    _shot(app, "04_search_cleared_restored.png")

    app.destroy()
    print(f"QA profile root (left for inspection): {_QA_ROOT}")
    print(f"Screenshots: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
