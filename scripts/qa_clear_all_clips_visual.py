"""CACHEVAULT SAFE CLEAR-ALL CLIPS — isolated QA walkthrough + regression proof.

Drives the real ``CacheVaultApp`` from this worktree against a throwaway,
self-contained QA profile (LOCALAPPDATA/TEMP/USERPROFILE redirected, so the
user's real vault is never touched) and proves the exact failure that manual
SQLite deletion caused does NOT happen through the supported feature:

  phase 1  seed a mixed dataset (text, favorites, collection members, images,
           a duplicate) -> open the real All Clips sidebar menu -> confirm the
           exact-count dialog -> All Clips empty -> Recently Removed holds the
           moved clips -> capture a new text clip -> capture a new image clip
  phase 2  relaunch the SAME profile in a NEW process -> prove the post-clear
           state persisted and that capture still works after restart

Running phase 2 as a separate process is deliberate: it is a genuine restart,
not a second window inside one interpreter.

Capture is paused throughout, so the live OS clipboard is never read. No
network, no packaging, no user profile.

Run:
    python scripts/qa_clear_all_clips_visual.py --out DIR --profile DIR --phase 1
    python scripts/qa_clear_all_clips_visual.py --out DIR --profile DIR --phase 2
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path


def _arg(name: str, default: str | None = None) -> str | None:
    flag = f"--{name}"
    if flag in sys.argv:
        return sys.argv[sys.argv.index(flag) + 1]
    return default


_PHASE = int(_arg("phase", "1"))
_PROFILE = Path(_arg("profile") or "").resolve()
_OUT = Path(_arg("out") or "").resolve()
_PROFILE.mkdir(parents=True, exist_ok=True)
_OUT.mkdir(parents=True, exist_ok=True)

# --- Isolate the profile BEFORE importing cache_vault modules that read it. -
os.environ["LOCALAPPDATA"] = str(_PROFILE / "LocalAppData")
os.environ["TEMP"] = str(_PROFILE / "Temp")
os.environ["TMP"] = str(_PROFILE / "Temp")
os.environ["USERPROFILE"] = str(_PROFILE / "UserProfile")
os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"
(_PROFILE / "Temp").mkdir(parents=True, exist_ok=True)

_WORKTREE = Path(__file__).resolve().parents[1]
if str(_WORKTREE) not in sys.path:
    sys.path.insert(0, str(_WORKTREE))

import customtkinter as ctk  # noqa: E402,F401

from cache_vault.core import sidebar_menu_context as smc  # noqa: E402
from cache_vault.core import storage as S  # noqa: E402
from cache_vault.core.settings import Settings  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402
from cache_vault.core.search import SearchQuery  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402
from cache_vault.ui import sidebar_context  # noqa: E402
from cache_vault.ui.shell import CacheVaultApp  # noqa: E402
from cache_vault.ui.theme import apply_app_theme  # noqa: E402
from tests.tk_support import wait_for_refresh  # noqa: E402

from PIL import Image, ImageGrab  # noqa: E402

DB = _PROFILE / "vault.db"
CHECKS: list[str] = []


def _check(label: str, ok: bool, detail: str = "") -> None:
    CHECKS.append(f"{'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    print(f"[{'PASS' if ok else 'FAIL'}] {label} {detail}")


def _pump(app, n: int = 6) -> None:
    for _ in range(n):
        app.update_idletasks()
        app.update()


def _settle(app, expected_visible=None) -> None:
    app._do_refresh_sync()
    if expected_visible is None:
        wait_for_refresh(app)
    else:
        wait_for_refresh(
            app,
            ui_settled=lambda: len(getattr(app, "_visible_clip_ids", [])) == expected_visible,
            ui_description=f"visible clip count == {expected_visible}",
        )
    _pump(app)


def _raise(app) -> None:
    try:
        app.lift()
        app.attributes("-topmost", True)
        app.focus_force()
        _pump(app, 2)
    except Exception:  # noqa: BLE001
        pass


def _shot(app, name: str) -> None:
    _raise(app)
    _pump(app, 3)
    x, y = app.winfo_rootx(), app.winfo_rooty()
    w, h = app.winfo_width(), app.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(_OUT / name)
    print(f"[shot] {_OUT / name}")


def _png_bytes(w: int, h: int, color) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _seed(vault) -> dict:
    """Mixed dataset: text, favorites, collection members, images, duplicate."""
    text = [
        ("Quarterly report draft — Q3 figures", "Word.exe"),
        ("https://github.com/theprooffoundry/cachevault", "chrome.exe"),
        ("def clear_all(query): return vault.clear_all_clips(ids)", "cursor.exe"),
        ("git status --porcelain", "WindowsTerminal.exe"),
        ("ssh -i ~/.ssh/id_ed25519 deploy@cachevault.example", "WindowsTerminal.exe"),
        ("Release notes — safe clear-all clips", "Word.exe"),
        ("invoice-2026-08-0042.pdf", "explorer.exe"),
    ]
    ids = []
    for content, src in text:
        c = vault.capture(content, source_app=src, force=True)
        if c:
            ids.append(c.id)

    # A duplicate of an earlier clip (non-consecutive, so it is a real row).
    dup = vault.capture(text[0][0], source_app="Word.exe", force=True)
    if dup:
        ids.append(dup.id)

    # Two image clips with real managed asset files.
    img_ids = []
    for i, color in enumerate(((190, 40, 40), (40, 90, 190))):
        c = vault.capture_image(
            _png_bytes(120, 80, color), width=120, height=80,
            original_name=f"screenshot-{i + 1}.png", source_app="ShareX.exe", force=True,
        )
        if c:
            img_ids.append(c.id)
            ids.append(c.id)

    fav_ids = ids[:2]
    for cid in fav_ids:
        vault.set_favorite(cid, True)
    col_ids = ids[2:5]
    for cid in col_ids:
        vault.set_collection(cid, "Work")

    return {"all": ids, "images": img_ids, "favorites": fav_ids, "collection": col_ids}


def _all_clips_ctx(app):
    return sidebar_context.build_sidebar_invocation_context_for_window(app, S.FILTER_ALL, None)


def phase1() -> int:
    apply_app_theme()
    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    vault = Vault(storage=VaultStorage(DB), settings=settings)
    seeded = _seed(vault)

    app = CacheVaultApp(vault=vault)
    app.geometry("1280x860+70+50")
    app.deiconify()
    _pump(app)

    app._navigate_filter(S.FILTER_ALL)
    total = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    _settle(app)
    print(f"[info] seeded total active clips = {total}")
    _check("mixed dataset seeded (text + favorites + collection + images + duplicate)",
           total == len(seeded["all"]), f"active={total}")
    _check("image-backed clips have managed assets",
           all(vault.storage.has_clip_asset(i) for i in seeded["images"]),
           f"{len(seeded['images'])} assets")
    _shot(app, "01_all_clips_before_clear.png")

    # --- 1. the real sidebar menu, showing the real command label ----------
    ctx = _all_clips_ctx(app)
    labels = {c.key: c.label for c in smc.sidebar_command_matrix(ctx)}
    clear_label = labels.get(smc.CMD_CLEAR_ALL_CLIPS, "")
    print(f"[menu] {clear_label!r}")
    _check("menu exposes Clear All Clips with the exact count",
           str(total) in clear_label and "Recently Removed" in clear_label, clear_label)

    def _grab_menu() -> None:
        try:
            ImageGrab.grab().save(_OUT / "02_all_clips_menu_clear_all.png")
            print(f"[shot] {_OUT / '02_all_clips_menu_clear_all.png'} (full screen, menu posted)")
        finally:
            menu = getattr(app, "_active_popup_menu", None)
            if menu is not None:
                try:
                    menu.unpost()
                except Exception:  # noqa: BLE001
                    pass

    # tk_popup runs a nested event loop, so this after() fires while the real
    # menu is on screen; unposting lets tk_popup return.
    app.after(700, _grab_menu)
    x = app.winfo_rootx() + 150
    y = app.winfo_rooty() + 300
    sidebar_context.open_sidebar_menu(app, ctx, x, y)
    _pump(app)

    # --- 2. the confirmation dialog, with the exact count ------------------
    app._sidebar_clear_all_clips(_all_clips_ctx(app))
    for _ in range(40):
        _pump(app, 2)
    from cache_vault.ui.dialogs import ClearAllClipsDialog
    dialog = next(
        (w for w in app.winfo_children() if isinstance(w, ClearAllClipsDialog)), None,
    )
    _check("confirmation dialog opened before any mutation", dialog is not None)
    if dialog is None:
        app.destroy()
        return 1
    still = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    _check("nothing moved while the dialog is still open", still == total, f"active={still}")
    _raise(app)
    _pump(app, 3)
    dialog.update_idletasks()
    dialog.lift()
    _pump(app, 3)
    dx, dy = dialog.winfo_rootx(), dialog.winfo_rooty()
    dw, dh = dialog.winfo_width(), dialog.winfo_height()
    ImageGrab.grab(bbox=(dx, dy, dx + dw, dy + dh)).save(_OUT / "03_confirm_exact_count.png")
    print(f"[shot] {_OUT / '03_confirm_exact_count.png'}")

    # Confirm exactly the way the button does.
    dialog._finish()
    for _ in range(40):
        _pump(app, 2)
    _settle(app)

    # --- 3. All Clips empty ------------------------------------------------
    after = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    _check("All Clips is empty after confirming", after == 0, f"active={after}")
    _shot(app, "04_all_clips_empty.png")

    # --- 4. Recently Removed holds them -----------------------------------
    rr = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED))
    _check("Recently Removed holds every cleared clip", rr == total, f"recently_removed={rr}")
    app._navigate_filter(S.FILTER_RECENTLY_REMOVED)
    _settle(app)
    _shot(app, "05_recently_removed_after_clear.png")

    # --- 5. invariants: nothing destroyed ---------------------------------
    _check("managed asset files survived the clear",
           all(vault.storage.has_clip_asset(i) for i in seeded["images"]))
    _check("no dangling active favorites",
           vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_FAVORITES)) == 0)
    _check("no dangling active collection members",
           vault.storage.list_collections() == [])

    # --- 6. THE REGRESSION: capture still works ---------------------------
    app._navigate_filter(S.FILTER_ALL)
    _settle(app)
    new_text = vault.capture("NEW TEXT CLIP captured after Clear All Clips", force=True)
    _check("new text clip captured after clearing", new_text is not None)
    _settle(app)
    _shot(app, "06_new_text_clip_after_clear.png")

    new_img = vault.capture_image(
        _png_bytes(140, 90, (30, 150, 120)), width=140, height=90,
        original_name="after-clear.png", source_app="ShareX.exe", force=True,
    )
    _check("new image clip captured after clearing", new_img is not None)
    _check("new image clip has a managed asset",
           new_img is not None and vault.storage.has_clip_asset(new_img.id))
    _settle(app)
    _shot(app, "07_new_image_clip_after_clear.png")

    live = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    _check("post-clear captures are the only active clips", live == 2, f"active={live}")

    # Quit normally.
    app.destroy()
    vault.close()
    print("[phase1] app closed normally")
    return 0


def phase2() -> int:
    apply_app_theme()
    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    vault = Vault(storage=VaultStorage(DB), settings=settings)

    app = CacheVaultApp(vault=vault)
    app.geometry("1280x860+70+50")
    app.deiconify()
    _pump(app)
    app._navigate_filter(S.FILTER_ALL)
    _settle(app)

    live = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    rr = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_RECENTLY_REMOVED))
    _check("post-clear state survived the restart", live == 2, f"active={live}")
    _check("Recently Removed survived the restart", rr > 0, f"recently_removed={rr}")

    clip = vault.capture("CAPTURED AFTER RESTART — vault still works", force=True)
    _check("capture still works after quit and relaunch", clip is not None)
    _settle(app)
    live2 = vault.storage.count_clips(SearchQuery(filter_name=S.FILTER_ALL))
    _check("new clip is visible after restart", live2 == 3, f"active={live2}")
    _shot(app, "08_after_restart_capture_works.png")

    app.destroy()
    vault.close()
    print("[phase2] app closed normally")
    return 0


def main() -> int:
    rc = phase1() if _PHASE == 1 else phase2()
    print("\n=== CHECKS ===")
    for line in CHECKS:
        print(line)
    failed = [c for c in CHECKS if c.startswith("FAIL")]
    print(f"\nphase {_PHASE}: {len(CHECKS) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed or rc else 0


if __name__ == "__main__":
    raise SystemExit(main())
