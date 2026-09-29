"""CV-VL2-A-HW1 — packaged-runtime Vault Lock qualification (Windows).

Runs the frozen CV-VL2-A package against a disposable profile that is created
under %TEMP%, never the real %LOCALAPPDATA%\\CacheVault profile. Capture is
paused and auto-capture disabled inside that profile, so the live clipboard is
never ingested and no real vault data is read, written, or displayed.

Evidence classes produced by this harness:
  SOURCE_ID     - canonical 13-file candidate identity recomputed here
  PACKAGE_ID    - SHA-256 of the exact package binary executed
  RUNTIME_EVENT - rows written by the running app into that profile's event log
  RUNTIME_HTTP  - HTTP status returned by the running app's Mobile Bridge
  RUNTIME_IMAGE - window-scoped PrintWindow capture of the app's own window
  MESSAGE_LEVEL - synthetic OS message delivered to the app's real WNDPROC

The credential is generated per run and never written to evidence, the repo, or
the profile; only the verifier that the product itself stores is persisted.

Deliberately does NOT perform a real interactive-session lock. That step is
owner-gated (-real-session-lock) because it locks the operator's desktop.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes
import hashlib
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(r"C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2")
DEFAULT_EXE = Path(
    r"C:\Users\KickA\AppData\Local\Temp"
    r"\cv-vl2-rb1-544f9443dbb741af9b46fa416d39c127\dist\CacheVault.exe"
)
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results.json"

EXPECTED_SOURCE_SHA = "2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877"
EXPECTED_PACKAGE_SHA = (
    "4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519"
)
CANONICAL_FILES = (
    "cache_vault/core/mobile/bridge.py",
    "cache_vault/core/settings.py",
    "cache_vault/core/vault_lock.py",
    "cache_vault/modules/registry.py",
    "cache_vault/ui/dialogs.py",
    "cache_vault/ui/shell.py",
    "cache_vault/ui/vault_lock.py",
    "cache_vault/ui/windows_session_lock.py",
    "review/CV-VAULT-LOCK-2-20260924/RECONCILIATION.md",
    "tests/test_command_center_app.py",
    "tests/test_mobile_bridge.py",
    "tests/test_vault_lock.py",
    "tests/test_vault_lock_ui.py",
)
WINDOW_TITLE = "Cache Vault"
BRIDGE_PORT = 18742
BRIDGE_HOST = "127.0.0.1"

WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_LOCK = 0x7
WTS_SESSION_UNLOCK = 0x8
SW_MINIMIZE = 6
WM_CLOSE = 0x0010

user32 = ctypes.WinDLL("user32", use_last_error=True)

_results: dict = {"steps": [], "observed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")}


def note(step: str, **fields) -> None:
    entry = {"step": step, "at": time.strftime("%H:%M:%S"), **fields}
    _results["steps"].append(entry)
    print(json.dumps(entry, sort_keys=True), flush=True)


def persist() -> None:
    RESULTS.write_text(json.dumps(_results, indent=2, sort_keys=True), encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_source_identity() -> str:
    """Recompute the canonical 13-file candidate identity, per the procedure
    recorded in review/CV-VL2-A-HASH-R1-20260925/CANDIDATE_CUSTODY_RECONCILIATION.md:
    a UTF-8 record stream of "<relative-path>\\t<raw-file-sha256>\\n" over the
    path list sorted by the ordinal bytes of its UTF-8 encoding.
    """
    h = hashlib.sha256()
    for rel in sorted(CANONICAL_FILES, key=lambda p: p.encode("utf-8")):
        digest = sha256_file(REPO / rel)
        h.update(f"{rel}\t{digest}\n".encode("utf-8"))
    return h.hexdigest()


def audit_aggregate_identity() -> str:
    """Reproduce the earlier audit's byte-level encoding (CV-DT1A section 13).

    This is retained as a second, independently reproducible identity so the
    two recorded digests can be told apart rather than confused.
    """
    h = hashlib.sha256()
    h.update(b"BASE=3af328424c39d97d4af54156672a2e4b2d2b8c43\n")
    for rel in sorted(CANONICAL_FILES, key=lambda p: p.encode("utf-8")):
        raw = (REPO / rel).read_bytes()
        h.update(rel.encode("utf-8"))
        h.update(b"\x00")
        h.update(len(raw).to_bytes(8, "little"))
        h.update(raw)
    return h.hexdigest()


# --------------------------------------------------------------------------- #
# profile
# --------------------------------------------------------------------------- #

def seed_profile(profile: Path, pin: str) -> Path:
    """Create the disposable profile with the lock enabled, using the
    product's own Settings/set_lock_secret so the on-disk format is authentic.
    """
    profile.mkdir(parents=True, exist_ok=True)
    os.environ["LOCALAPPDATA"] = str(profile)
    sys.path.insert(0, str(REPO))
    from cache_vault.core.settings import Settings
    from cache_vault.core import vault_lock

    settings = Settings()
    settings.capture_paused = True          # never ingest the live clipboard
    settings.auto_capture_enabled = False
    settings.block_sensitive_auto_capture = True
    settings.first_use_guide_dismissed = True
    settings.mobile_access_enabled = True   # loopback-only, for the 423 probe
    settings.mobile_access_bind_host = BRIDGE_HOST
    settings.mobile_access_port = BRIDGE_PORT
    settings.vault_lock_when_minimized = True
    settings.vault_lock_auto_minutes = 0
    vault_lock.set_lock_secret(settings, pin, mode="pin")
    settings.save()
    settings_file = profile / "CacheVault" / "settings.json"
    if not settings_file.exists():
        raise SystemExit(f"profile seed failed: {settings_file} was not written")
    return settings_file


def profile_paths(profile: Path) -> dict:
    base = profile / "CacheVault"
    dbs = sorted(base.glob("*.db"))
    return {"base": base, "db": dbs[0] if dbs else None}


# --------------------------------------------------------------------------- #
# observation
# --------------------------------------------------------------------------- #

def event_rows(db: Path) -> list[dict]:
    if not db or not db.exists():
        return []
    uri = f"file:{db.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5.0)
    try:
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT created_at, event_type, details FROM events "
            "ORDER BY created_at ASC, rowid ASC",
        ).fetchall()
    finally:
        con.close()
    out = []
    for r in rows:
        try:
            details = json.loads(r["details"]) if r["details"] else {}
        except (TypeError, ValueError):
            details = {}
        out.append({
            "created_at": r["created_at"],
            "event_type": r["event_type"],
            "reason": details.get("reason"),
            "method": details.get("method"),
            "mode": details.get("mode"),
            "canonical_event": details.get("canonical_event"),
        })
    return out


def wait_for_event(db: Path, event_type: str, *, timeout: float,
                   after: int = 0, reason: str | None = None) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        rows = event_rows(db)
        for row in rows[after:]:
            if row["event_type"] != event_type:
                continue
            if reason is not None and row["reason"] != reason:
                continue
            return row
        time.sleep(0.4)
    return None


def find_hwnd(title_sub: str, *, timeout: float = 30.0) -> int:
    import win32gui

    deadline = time.time() + timeout
    while time.time() < deadline:
        found: list[int] = []

        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and title_sub.lower() in win32gui.GetWindowText(hwnd).lower():
                found.append(hwnd)
            return True

        win32gui.EnumWindows(cb, None)
        if found:
            return found[0]
        time.sleep(0.4)
    return 0


def capture_window(hwnd: int, out: Path) -> bool:
    rc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "capture_window.py"),
         WINDOW_TITLE, str(out)],
        cwd=str(REPO), capture_output=True, text=True, timeout=60,
    )
    return rc.returncode == 0 and out.exists()


def bridge_probe(path: str = "/mobile/v1/pair-device", *, body: dict | None = None,
                 method: str = "POST") -> dict:
    url = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}{path}"
    data = json.dumps(body or {"device_id": "hw1-probe", "device_name": "hw1"}).encode()
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return {"status": resp.status, "body": resp.read(200).decode("utf-8", "replace")}
    except urllib.error.HTTPError as exc:
        return {"status": exc.code, "body": exc.read(200).decode("utf-8", "replace")}
    except Exception as exc:  # noqa: BLE001
        return {"status": None, "error": f"{type(exc).__name__}: {exc}"}


# --------------------------------------------------------------------------- #
# input
# --------------------------------------------------------------------------- #

def foreground_is(hwnd: int) -> bool:
    user32.GetForegroundWindow.restype = ctypes.c_void_p
    return int(user32.GetForegroundWindow() or 0) == int(hwnd)


def client_size(hwnd: int) -> tuple[int, int]:
    import win32gui

    _l, _t, right, bottom = win32gui.GetClientRect(hwnd)
    return right, bottom


def click_screen(x: int, y: int) -> None:
    """Move the real cursor to screen (x, y) and perform a physical left
    click. This is the repo's proven input pattern (scripts/secure_vault_smoke.py):
    a real mouse event goes through the full Windows input pipeline, so Tk's
    WNDPROC receives it and CTkEntry's <Button-1> binding calls focus_set() —
    which posted WM_LBUTTONDOWN does not reliably trigger.
    """
    user32.SetCursorPos(x, y)
    time.sleep(0.15)
    user32.mouse_event(0x0002, 0, 0, 0, 0)   # MOUSEEVENTF_LEFTDOWN
    user32.mouse_event(0x0004, 0, 0, 0, 0)   # MOUSEEVENTF_LEFTUP
    time.sleep(0.5)


def app_top_level_windows(pid: int) -> list[dict]:
    """Every visible AND hidden top-level window owned by the app process.

    A modal dialog or helper window holding keyboard focus would explain why
    injected input never reaches the lock screen even though the main window is
    reported as foreground.
    """
    import win32gui
    import win32process

    out: list[dict] = []

    def cb(hwnd, _):
        try:
            _thread, owner = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:  # noqa: BLE001
            return True
        if owner != pid:
            return True
        out.append({
            "hwnd": hwnd,
            "class": win32gui.GetClassName(hwnd),
            "title": win32gui.GetWindowText(hwnd),
            "visible": bool(win32gui.IsWindowVisible(hwnd)),
            "enabled": bool(win32gui.IsWindowEnabled(hwnd)),
            "rect": list(win32gui.GetWindowRect(hwnd)),
        })
        return True

    win32gui.EnumWindows(cb, None)
    return out


def attempt_unlock(hwnd: int, db: Path, pin: str, *, pid: int | None = None) -> dict:
    """Unlock the disposable instance.  Tries two strategies in sequence and
    proves success via the product's own vault_unlocked event:

    Strategy A — Post WM_KEYDOWN/WM_KEYUP for each digit + Enter directly to
    the Tk hwnd.  The child process's message loop calls TranslateMessage
    (generating WM_CHAR) and DispatchMessage, so the entry that has Tk focus
    from startup focus_unlock() receives the characters.  No cursor movement
    or foreground assertion is needed because the messages go straight to
    the hwnd's own queue.

    Strategy B — Real-cursor click on the entry (CTkEntry <Button-1> →
    focus_set), keybd_event for the digits, then real-cursor click on the
    "Unlock Vault" button.  This is the repo's proven GUI-automation path.
    """
    import win32gui

    info: dict = {}
    before = len(event_rows(db))

    # ---- Strategy A: post keyboard messages directly to the hwnd ----
    info["strategy_a"] = "post_wm_keydown"
    for ch in pin:
        vk = ord(ch.upper())
        user32.PostMessageW(hwnd, 0x0100, vk, 0x30000001)  # WM_KEYDOWN
        time.sleep(0.03)
        user32.PostMessageW(hwnd, 0x0101, vk, 0xC0000001)  # WM_KEYUP
        time.sleep(0.03)
    time.sleep(0.3)
    info["capture_after_postmsg_typing"] = capture_window(
        hwnd, HERE / "03_after_postmsg_typing.png")
    # Enter via WM_KEYDOWN
    user32.PostMessageW(hwnd, 0x0100, 0x0D, 0x30000001)  # WM_KEYDOWN VK_RETURN
    time.sleep(0.03)
    user32.PostMessageW(hwnd, 0x0101, 0x0D, 0xC0000001)  # WM_KEYUP

    unlocked = wait_for_event(db, "vault_unlocked", timeout=8, after=before)
    if unlocked:
        info["unlocked_event"] = unlocked
        info["strategy_that_worked"] = "A"
        info["failed_event"] = None
        return info

    failed_a = wait_for_event(db, "vault_unlock_failed", timeout=2, after=before)
    info["strategy_a_failed_event"] = failed_a

    # ---- Strategy B: real-cursor click + keybd_event + button click ----
    info["strategy_b"] = "real_cursor"
    try:
        user32.SetForegroundWindow(hwnd)
    except Exception:
        pass
    time.sleep(0.8)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)

    width, height = client_size(hwnd)
    info["foreground_before_click"] = foreground_is(hwnd)
    info["client"] = [width, height]
    info["window_rect"] = list(win32gui.GetWindowRect(hwnd))
    origin = win32gui.ClientToScreen(hwnd, (0, 0))

    entry_x = origin[0] + width // 2
    entry_y = origin[1] + int(height * 0.647)
    btn_x = origin[0] + width // 2
    btn_y = origin[1] + int(height * 0.73)

    pt = ctypes.wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    saved_cursor = (pt.x, pt.y)
    info["entry_screen_click"] = [entry_x, entry_y]
    info["button_screen_click"] = [btn_x, btn_y]

    # Clear any partial digits from strategy A before re-typing
    # (select-all + delete via keybd_event)
    user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
    user32.keybd_event(0x41, 0, 0, 0)   # 'A' down
    user32.keybd_event(0x41, 0, 2, 0)   # 'A' up
    user32.keybd_event(0x11, 0, 2, 0)   # Ctrl up
    time.sleep(0.1)
    user32.keybd_event(0x2E, 0, 0, 0)   # Delete down
    user32.keybd_event(0x2E, 0, 2, 0)   # Delete up
    time.sleep(0.1)

    click_screen(entry_x, entry_y)
    info["foreground_after_click"] = foreground_is(hwnd)

    user32.SetForegroundWindow(hwnd)
    time.sleep(0.2)
    type_secret(pin)
    time.sleep(0.5)
    info["foreground_after_typing"] = foreground_is(hwnd)
    info["capture_after_typing"] = capture_window(hwnd, HERE / "04_after_typing.png")

    # Click the Unlock Vault button
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.1)
    click_screen(btn_x, btn_y)

    unlocked = wait_for_event(db, "vault_unlocked", timeout=12, after=before)
    failed = None if unlocked else wait_for_event(
        db, "vault_unlock_failed", timeout=3, after=before)
    info["unlocked_event"] = unlocked
    info["failed_event"] = failed
    if unlocked:
        info["strategy_that_worked"] = "B"

    user32.SetCursorPos(saved_cursor[0], saved_cursor[1])
    return info


def type_secret(value: str) -> None:
    for ch in value:
        vk = ord(ch.upper())
        user32.keybd_event(vk, 0, 0, 0)
        user32.keybd_event(vk, 0, 2, 0)
        time.sleep(0.04)


def press(vk: int) -> None:
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)


def post_session_message(hwnd: int, wparam: int) -> bool:
    return bool(user32.PostMessageW(hwnd, WM_WTSSESSION_CHANGE, wparam, 0))


def steal_foreground() -> int:
    """Make a window belonging to THIS process (the harness console) the
    foreground window.  The app's <FocusOut> handler checks whether the new
    foreground window's PID differs from the app's own PID and, if so, calls
    _lock_now(reason="app_background").  Returns the console hwnd or 0.
    """
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    hwnd_console = kernel32.GetConsoleWindow()
    if hwnd_console:
        user32.SetForegroundWindow(hwnd_console)
        time.sleep(0.3)
    return int(hwnd_console or 0)


def minimize_window(hwnd: int) -> bool:
    """Minimize the app window (SW_MINIMIZE) to trigger the <Unmap> handler,
    which calls _lock_now(reason="minimized") when vault_lock_when_minimized
    is enabled.  Returns True if ShowWindow succeeded."""
    return bool(user32.ShowWindow(hwnd, SW_MINIMIZE))


def restore_window(hwnd: int) -> bool:
    """Restore a minimized window back to its normal position."""
    return bool(user32.ShowWindow(hwnd, 1))  # SW_SHOWNORMAL


# --------------------------------------------------------------------------- #
# steps
# --------------------------------------------------------------------------- #

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exe", default=str(DEFAULT_EXE))
    ap.add_argument("--profile", default=None)
    ap.add_argument("--real-session-lock", action="store_true",
                    help="owner-gated: locks the operator's real desktop")
    ap.add_argument("--keep-running", action="store_true")
    args = ap.parse_args()

    exe = Path(args.exe)
    _results["exe"] = str(exe)

    identity = canonical_source_identity()
    aggregate = audit_aggregate_identity()
    _results["source_sha256"] = identity
    _results["source_sha256_matches_gate"] = identity == EXPECTED_SOURCE_SHA
    _results["audit_aggregate_sha256"] = aggregate
    note("source_identity", sha256=identity, matches=identity == EXPECTED_SOURCE_SHA,
         audit_aggregate=aggregate)

    if not exe.exists():
        note("package_missing", path=str(exe))
        persist()
        return 1
    pkg = sha256_file(exe)
    _results["package_sha256"] = pkg
    _results["package_sha256_matches_gate"] = pkg == EXPECTED_PACKAGE_SHA
    note("package_identity", sha256=pkg, bytes=exe.stat().st_size,
         matches=pkg == EXPECTED_PACKAGE_SHA)
    persist()

    profile = Path(args.profile) if args.profile else (
        Path(os.environ.get("TEMP", r"C:\Windows\Temp")) / f"cv-vl2-hw1-{secrets.token_hex(8)}"
    )
    pin = "".join(secrets.choice("1234567890") for _ in range(6))
    settings_file = seed_profile(profile, pin)
    paths = profile_paths(profile)
    _results["profile"] = str(profile)
    _results["settings_file"] = str(settings_file)
    note("profile_seeded", profile=str(profile), settings=str(settings_file),
         db=str(paths["db"]), capture_paused=True, credential="not recorded")

    proc = subprocess.Popen([str(exe), "--profile-dir", str(profile)])
    _results["pid"] = proc.pid
    hwnd = find_hwnd(WINDOW_TITLE, timeout=90)
    note("launched", pid=proc.pid, hwnd=hwnd, window_found=bool(hwnd))
    persist()
    if not hwnd:
        proc.terminate()
        return 1

    # The database does not exist until the app creates it, so resolve it now.
    db = None
    for _ in range(40):
        db = profile_paths(profile)["db"]
        if db and db.exists():
            break
        time.sleep(0.5)
    _results["db"] = str(db)
    note("database_resolved", db=str(db))
    time.sleep(2.0)

    # 1. startup lock
    startup = wait_for_event(db, "vault_locked", timeout=20, reason="startup")
    note("startup_lock", event=startup)
    _results["startup_lock_ok"] = bool(startup)

    shot = HERE / "01_startup_locked.png"
    _results["startup_capture_ok"] = capture_window(hwnd, shot)
    note("startup_capture", path=str(shot), ok=_results["startup_capture_ok"])

    # 2. bridge while locked -> 423 vault_locked
    locked_probe = bridge_probe()
    _results["bridge_locked"] = locked_probe
    note("bridge_while_locked", **locked_probe)

    # 3. unlock with the throwaway credential
    unlock = attempt_unlock(hwnd, db, pin, pid=proc.pid)
    _results["unlock"] = unlock
    _results["unlock_ok"] = bool(unlock["unlocked_event"])
    note("unlock", **unlock)
    persist()
    if not unlock["unlocked_event"]:
        _results["events"] = event_rows(db)
        persist()
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        proc.terminate()
        note("aborted", reason="unlock did not land; later phases need an unlocked session")
        return 1

    # 4. bridge while unlocked -> must not be 423
    open_probe = bridge_probe()
    _results["bridge_unlocked"] = open_probe
    note("bridge_while_unlocked", **open_probe)

    # 5. session-lock trigger (message-level, through the real WNDPROC)
    before = len(event_rows(db))
    posted = post_session_message(hwnd, WTS_SESSION_LOCK)
    relock = wait_for_event(db, "vault_locked", timeout=15, after=before)
    _results["session_lock_message_posted"] = posted
    _results["session_lock_relock"] = relock
    note("session_lock_trigger", posted=posted, event=relock)

    # 6. negative control: WTS unlock must not unlock the vault
    before = len(event_rows(db))
    post_session_message(hwnd, WTS_SESSION_UNLOCK)
    time.sleep(3.0)
    bogus = wait_for_event(db, "vault_unlocked", timeout=2, after=before)
    _results["session_unlock_did_not_open"] = bogus is None
    note("session_unlock_negative_control", unexpected_unlock=bogus)

    # 7. bridge after WTS re-lock -> 423 again
    relock_probe = bridge_probe()
    _results["bridge_after_wts_relock"] = relock_probe
    note("bridge_after_wts_relock", **relock_probe)

    shot = HERE / "02_after_wts_lock.png"
    _results["wts_relock_capture_ok"] = capture_window(hwnd, shot)
    note("wts_relock_capture", path=str(shot), ok=_results["wts_relock_capture_ok"])

    # 8. re-unlock for the foreground-loss trigger test
    unlock2 = attempt_unlock(hwnd, db, pin)
    _results["unlock2"] = unlock2
    _results["unlock2_ok"] = bool(unlock2["unlocked_event"])
    note("unlock2", **unlock2)
    persist()
    if not unlock2["unlocked_event"]:
        _results["events"] = event_rows(db)
        persist()
        note("skipped_foreground_loss", reason="second unlock did not land")
    else:
        # 9. foreground-loss trigger: steal foreground to the console window
        before = len(event_rows(db))
        console_hwnd = steal_foreground()
        time.sleep(0.5)  # allow the 150ms after() callback to fire
        fg_relock = wait_for_event(db, "vault_locked", timeout=10, after=before)
        _results["foreground_loss_relock"] = fg_relock
        _results["foreground_loss_console_hwnd"] = console_hwnd
        note("foreground_loss_trigger", console_hwnd=console_hwnd, event=fg_relock)

        # 10. bridge after foreground-loss re-lock -> 423
        fg_relock_probe = bridge_probe()
        _results["bridge_after_fg_relock"] = fg_relock_probe
        note("bridge_after_fg_relock", **fg_relock_probe)

    # 11. re-unlock for the minimize trigger test
    unlock3 = attempt_unlock(hwnd, db, pin)
    _results["unlock3"] = unlock3
    _results["unlock3_ok"] = bool(unlock3["unlocked_event"])
    note("unlock3", **unlock3)
    persist()
    if not unlock3["unlocked_event"]:
        _results["events"] = event_rows(db)
        persist()
        note("skipped_minimize", reason="third unlock did not land")
    else:
        # 12. minimize trigger
        before = len(event_rows(db))
        restore_window(hwnd)
        time.sleep(0.3)
        minimize_window(hwnd)
        time.sleep(1.0)
        min_relock = wait_for_event(db, "vault_locked", timeout=10, after=before,
                                    reason="minimized")
        _results["minimize_relock"] = min_relock
        note("minimize_trigger", event=min_relock)
        restore_window(hwnd)
        time.sleep(0.5)

        # 13. bridge after minimize re-lock -> 423
        min_relock_probe = bridge_probe()
        _results["bridge_after_min_relock"] = min_relock_probe
        note("bridge_after_min_relock", **min_relock_probe)

    _results["events"] = event_rows(db)
    persist()

    if args.real_session_lock:
        note("real_session_lock", action="initiated_by_owner_gate")
        os.system("rundll32.exe user32.dll,LockWorkStation")
        time.sleep(5)
        _results["events_after_real_lock"] = event_rows(db)
        persist()

    if not args.keep_running:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.terminate()
        note("closed", exit_code=proc.poll())
    persist()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
