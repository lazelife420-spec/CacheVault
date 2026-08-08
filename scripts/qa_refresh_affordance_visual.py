"""CACHEVAULT ALL CLIPS REFRESH AFFORDANCE — isolated QA visual walkthrough.

Launches the real CacheVaultApp from this worktree against a throwaway,
self-contained QA profile (LOCALAPPDATA/TEMP/USERPROFILE redirected to a temp
dir so the user's real profile is never touched) and captures the page-level
Refresh control across its states:

  1. All Clips with Refresh visible alongside Search, Sort/Type and Cards/Grid
     (proves the controls coexist without crowding and that Refresh is visually
     distinct from the Cards/Grid view toggle)
  2. a zoomed crop of the toolbar rows so Refresh vs Cards/Grid is unmistakable
  3. Refresh busy state (control disabled, "⟳ Refreshing…", indicator shown)
  4. Refresh complete (control back to normal, results usable)
  5. Grid view with Refresh still present (coexists across view modes)

The app is seeded with deterministic QA clips only; capture is paused so the
live OS clipboard is never read. No network, no user profile, no packaging.

Run:
    python scripts/qa_refresh_affordance_visual.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# --- Isolate the profile BEFORE importing cache_vault modules that read it. -
_QA_ROOT = Path(tempfile.mkdtemp(prefix="cachevault-qa-refresh-"))
os.environ["LOCALAPPDATA"] = str(_QA_ROOT / "LocalAppData")
os.environ["TEMP"] = str(_QA_ROOT / "Temp")
os.environ["TMP"] = str(_QA_ROOT / "Temp")
os.environ["USERPROFILE"] = str(_QA_ROOT / "UserProfile")
(_QA_ROOT / "Temp").mkdir(parents=True, exist_ok=True)

# Make the worktree source importable when run as a script from the worktree.
_WORKTREE = Path(__file__).resolve().parents[1]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

import customtkinter as ctk  # noqa: E402,F401

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

OUT = _WORKTREE / "qa_refresh_screenshots"
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


def _raise(app) -> None:
    """Keep the QA window unobscured so ImageGrab never captures the desktop
    wallpaper instead of the app (seen after the mainloop pump drops topmost)."""
    try:
        app.lift()
        app.attributes("-topmost", True)
        app.focus_force()
        app.update_idletasks()
        app.update()
    except Exception:  # noqa: BLE001
        pass


def _shot(app, name: str) -> None:
    _raise(app)
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


def _shot_toolbar(app, name: str) -> None:
    """Zoomed crop of just the toolbar band so Refresh vs Cards/Grid is clear."""
    _raise(app)
    app.update_idletasks()
    app.update()
    if ImageGrab is None:
        print(f"[skip] PIL.ImageGrab unavailable — no toolbar crop for {name}")
        return
    row = app._toolbar_row2
    x = app.winfo_rootx()
    y = row.winfo_rooty() - 40
    w = app.winfo_width()
    h = 130
    img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
    path = OUT / name
    img.save(path)
    print(f"[shot] {path}")


def main() -> int:
    apply_app_theme()
    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    storage = VaultStorage(_QA_ROOT / "vault.db")
    vault = Vault(storage=storage, settings=settings)

    seeds = [
        ("Quarterly report draft — Q3 figures", "Word.exe"),
        ("https://github.com/theprooffoundry/cachevault", "chrome.exe"),
        ("def refresh_clips(query): return vault.list_clips(query)", "cursor.exe"),
        ("git status --porcelain", "WindowsTerminal.exe"),
        ("boilerplate marketing copy for the landing page hero", "Word.exe"),
        ("ssh -i ~/.ssh/id_ed25519 deploy@cachevault.example", "WindowsTerminal.exe"),
        ("Release notes — All Clips refresh affordance", "Word.exe"),
    ]
    for content, src in seeds:
        vault.capture(content, source_app=src, force=True)

    app = CacheVaultApp(vault=vault)
    app.geometry("1200x820+80+60")
    app.deiconify()
    app.update_idletasks()
    app.update()

    total = len(seeds)

    app._navigate_screen(FILTER_ALL)
    _settle(app, expected_visible=total)

    # 1. All Clips with all controls visible (Refresh coexisting, not crowded).
    _shot(app, "01_all_clips_refresh_visible.png")
    # 2. Zoomed toolbar crop: Refresh distinct from Cards/Grid.
    _shot_toolbar(app, "02_toolbar_refresh_vs_view_toggle.png")

    # 3. Busy state: invoke via the actual wired control command; refresh() sets
    #    the busy/disabled state synchronously, so paint one frame and capture
    #    before the background worker completes.
    cmd = app._refresh_btn.cget("command")
    cmd()
    app.update_idletasks()
    app.update()
    busy_state = str(app._refresh_btn.cget("state"))
    busy_text = app._refresh_btn.cget("text")
    indicator = app._page_header._refreshing_label.cget("text")
    print(f"[state] busy: control state={busy_state!r} text={busy_text!r} indicator={indicator!r}")
    _shot(app, "03_refresh_busy.png")
    _shot_toolbar(app, "04_refresh_busy_toolbar.png")

    # 4. Complete: settle and confirm the control returns to normal + results.
    wait_for_refresh(app)
    for _ in range(5):
        app.update_idletasks()
        app.update()
    done_state = str(app._refresh_btn.cget("state"))
    done_text = app._refresh_btn.cget("text")
    visible = len(getattr(app, "_visible_clip_ids", []))
    print(f"[state] done: control state={done_state!r} text={done_text!r} visible={visible}")
    _shot(app, "05_refresh_complete.png")

    # 5. Grid view: Refresh still present across view modes.
    app._set_view_mode("grid")
    _settle(app, expected_visible=total)
    _shot(app, "06_grid_view_refresh_present.png")
    _shot_toolbar(app, "07_grid_toolbar_refresh_present.png")

    app.destroy()
    print(f"QA profile root (left for inspection): {_QA_ROOT}")
    print(f"Screenshots: {OUT}")
    print(
        "SUMMARY: "
        f"busy_state={busy_state} busy_text={busy_text!r} indicator={indicator!r} | "
        f"done_state={done_state} done_text={done_text!r} visible_after={visible}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
