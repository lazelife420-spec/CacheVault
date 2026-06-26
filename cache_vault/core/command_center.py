"""Command Center — clipboard-powered automation with proof.

Phase 1: Hotkey Actions. A Hotkey Action ties a user-defined global shortcut
to a single safe vault action (open the vault, open Quick Paste, pause/resume
capture, save the clipboard to a Safe, run a Vault Macro, lock the vault).

This module is UI- and Windows-free so the data model, conflict detection,
dispatcher bookkeeping, and run log are fully unit-testable. The shell supplies
the concrete action handlers and owns the global-hotkey listener.

Core model:  Trigger -> Action -> Target -> Options -> Receipt
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Callable, Optional

from . import models, safe_io
from .hotkey import normalize_hotkey, parse_hotkey

# --- Action types ------------------------------------------------------------
ACTION_OPEN_VAULT = "open_vault"
ACTION_OPEN_QUICK_PASTE = "open_quick_paste"
ACTION_TOGGLE_CAPTURE = "toggle_capture"
ACTION_SAVE_CLIPBOARD_TO_SAFE = "save_clipboard_to_safe"
ACTION_MOVE_LATEST_TO_SAFE = "move_latest_to_safe"
ACTION_COPY_SELECTED = "copy_selected"
ACTION_COPY_SELECTED_CLEAN = "copy_selected_clean"
ACTION_PASTE_SELECTED = "paste_selected"
ACTION_TOGGLE_MOBILE = "toggle_mobile"
ACTION_RUN_MACRO = "run_macro"
ACTION_EXPORT_SELECTED = "export_selected"
ACTION_CREATE_RECEIPT = "create_receipt"
ACTION_LOCK_VAULT = "lock_vault"

# Target kinds — what the "Target" dropdown should offer for an action type.
TARGET_NONE = "none"
TARGET_SAFE = "safe"
TARGET_MACRO = "macro"

# Scope.
SCOPE_GLOBAL = "global"
SCOPE_APP = "app"
SCOPES = (SCOPE_GLOBAL, SCOPE_APP)

# Registration status (visible state of a global hotkey).
REG_UNKNOWN = "unknown"
REG_ACTIVE = "active"          # registered with the OS
REG_DISABLED = "disabled"      # action disabled, not registered
REG_FAILED = "failed"          # OS refused (likely already in use)
REG_CONFLICT = "conflict"      # collides with another Cache Vault shortcut
REG_RESERVED = "reserved"      # collides with a reserved system/app shortcut
REG_INVALID = "invalid"        # not a usable shortcut spec
REG_UNAVAILABLE = "unavailable"  # global hotkeys need Windows + pywin32

# Run results.
RESULT_OK = "ok"
RESULT_FAILED = "failed"
RESULT_BLOCKED = "blocked"


@dataclass(frozen=True)
class ActionSpec:
    """Static description of an action type."""

    key: str
    label: str
    description: str = ""
    target_kind: str = TARGET_NONE
    implemented: bool = False
    destructive: bool = False
    needs_confirmation: bool = False
    safe_when_locked: bool = False


# Only the actions marked ``implemented`` are offered in the editor and run by
# the dispatcher. Unimplemented entries are reserved names for later phases so
# the UI never advertises something that does not work yet.
ACTION_SPECS: dict[str, ActionSpec] = {
    ACTION_OPEN_VAULT: ActionSpec(
        ACTION_OPEN_VAULT, "Open Cache Vault",
        "Bring the vault window to the front.", implemented=True,
    ),
    ACTION_OPEN_QUICK_PASTE: ActionSpec(
        ACTION_OPEN_QUICK_PASTE, "Open Quick Paste",
        "Open the recent-clips picker at the cursor.", implemented=True,
    ),
    ACTION_TOGGLE_CAPTURE: ActionSpec(
        ACTION_TOGGLE_CAPTURE, "Pause / resume capture",
        "Toggle clipboard capture on or off.", implemented=True,
    ),
    ACTION_SAVE_CLIPBOARD_TO_SAFE: ActionSpec(
        ACTION_SAVE_CLIPBOARD_TO_SAFE, "Save current clipboard to Safe",
        "Save whatever is on the clipboard right now to a chosen Safe.",
        target_kind=TARGET_SAFE, implemented=True,
    ),
    ACTION_RUN_MACRO: ActionSpec(
        ACTION_RUN_MACRO, "Run Vault Macro",
        "Run a saved Vault Macro.", target_kind=TARGET_MACRO, implemented=True,
    ),
    ACTION_LOCK_VAULT: ActionSpec(
        ACTION_LOCK_VAULT, "Lock vault",
        "Lock the vault surface immediately.", implemented=True,
        safe_when_locked=True,
    ),
    # --- Reserved for later phases (not yet implemented) ---
    ACTION_MOVE_LATEST_TO_SAFE: ActionSpec(
        ACTION_MOVE_LATEST_TO_SAFE, "Move latest clip to Safe",
        target_kind=TARGET_SAFE,
    ),
    ACTION_COPY_SELECTED: ActionSpec(ACTION_COPY_SELECTED, "Copy selected clip"),
    ACTION_COPY_SELECTED_CLEAN: ActionSpec(
        ACTION_COPY_SELECTED_CLEAN, "Copy selected clip clean",
    ),
    ACTION_PASTE_SELECTED: ActionSpec(ACTION_PASTE_SELECTED, "Paste selected clip"),
    ACTION_TOGGLE_MOBILE: ActionSpec(ACTION_TOGGLE_MOBILE, "Toggle mobile bridge"),
    ACTION_EXPORT_SELECTED: ActionSpec(
        ACTION_EXPORT_SELECTED, "Export selected clip",
    ),
    ACTION_CREATE_RECEIPT: ActionSpec(
        ACTION_CREATE_RECEIPT, "Create stamped receipt",
    ),
}


def implemented_action_keys() -> list[str]:
    """Action types that actually run — the only ones offered in the editor."""
    return [k for k, spec in ACTION_SPECS.items() if spec.implemented]


def action_label(action_type: str) -> str:
    spec = ACTION_SPECS.get(action_type)
    return spec.label if spec else action_type


def action_target_kind(action_type: str) -> str:
    spec = ACTION_SPECS.get(action_type)
    return spec.target_kind if spec else TARGET_NONE


# --- Data model --------------------------------------------------------------
# Fields recomputed live each run; intentionally excluded from on-disk storage
# so command_center.json holds only action definitions/settings.
_RUNTIME_ONLY_FIELDS = ("registration_status", "registration_error")


@dataclass
class HotkeyAction:
    id: str = field(default_factory=models.new_id)
    name: str = ""
    enabled: bool = True
    hotkey: str = ""
    action_type: str = ACTION_OPEN_QUICK_PASTE
    target: str = ""          # safe_id or macro_id depending on action_type
    target_label: str = ""    # human-readable target, cached for display
    scope: str = SCOPE_GLOBAL
    created_at: str = field(default_factory=models.now_iso)
    updated_at: str = field(default_factory=models.now_iso)
    last_run_at: Optional[str] = None
    run_count: int = 0
    last_run_failed: bool = False
    # Registration state is recomputed live and kept in memory only; it is never
    # written to disk (see ``_RUNTIME_ONLY_FIELDS`` / ``to_dict``).
    registration_status: str = REG_UNKNOWN
    registration_error: str = ""

    def to_dict(self) -> dict:
        data = asdict(self)
        for runtime_field in _RUNTIME_ONLY_FIELDS:
            data.pop(runtime_field, None)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "HotkeyAction":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    @property
    def hotkey_display(self) -> str:
        return normalize_hotkey(self.hotkey) if self.hotkey else ""


def default_store_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "command_center.json"


class HotkeyActionStore:
    """Persisted Hotkey Actions in command_center.json (local only)."""

    def __init__(self, path: str | os.PathLike | None = None):
        self._path = Path(path or default_store_path())

    @property
    def path(self) -> Path:
        return self._path

    def load_all(self) -> list[HotkeyAction]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except OSError:
            return []
        except json.JSONDecodeError:
            safe_io.quarantine_corrupt(self._path)  # preserve, don't overwrite
            return []
        items = data.get("actions") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        return [HotkeyAction.from_dict(a) for a in items if isinstance(a, dict)]

    def save_all(self, actions: list[HotkeyAction]) -> None:
        payload = {"version": 1, "actions": [a.to_dict() for a in actions]}
        safe_io.atomic_write_text(
            self._path, json.dumps(payload, indent=2), keep_backup=True,
        )

    def get(self, action_id: str) -> Optional[HotkeyAction]:
        for a in self.load_all():
            if a.id == action_id:
                return a
        return None

    def upsert(self, action: HotkeyAction) -> HotkeyAction:
        action.updated_at = models.now_iso()
        actions = self.load_all()
        for i, a in enumerate(actions):
            if a.id == action.id:
                actions[i] = action
                self.save_all(actions)
                return action
        actions.append(action)
        self.save_all(actions)
        return action

    def delete(self, action_id: str) -> bool:
        actions = self.load_all()
        kept = [a for a in actions if a.id != action_id]
        if len(kept) == len(actions):
            return False
        self.save_all(kept)
        return True


# --- Conflict / reserved detection -------------------------------------------
def _canon(spec: str) -> str:
    return "+".join(p.lower() for p in normalize_hotkey(spec).split("+") if p)


def diagnose_action_hotkey(
    spec: str,
    *,
    self_id: str | None = None,
    other_actions: list[HotkeyAction] | None = None,
    reserved_specs: set[str] | frozenset[str] | None = None,
    win32_available: bool | None = None,
) -> tuple[str, str]:
    """Return ``(kind, message)`` for a candidate Hotkey Action shortcut.

    *kind* is one of REG_INVALID / REG_CONFLICT / REG_RESERVED /
    REG_UNAVAILABLE / "ok".
    """
    raw = (spec or "").strip()
    if not raw:
        return REG_INVALID, "Enter a shortcut like Ctrl+Alt+V"
    _mods, vk = parse_hotkey(raw)
    if vk is None:
        return REG_INVALID, "Add a key — use Ctrl/Alt/Shift + letter, F-key, or Space"
    canon = _canon(raw)
    for other in other_actions or []:
        if other.id == self_id or not other.hotkey:
            continue
        if _canon(other.hotkey) == canon:
            return REG_CONFLICT, f"Already used by '{other.name or 'another command'}'"
    reserved = {_canon(s) for s in (reserved_specs or set()) if s}
    if canon in reserved:
        return REG_RESERVED, "Reserved by Windows or another Cache Vault shortcut"
    if win32_available is None:
        try:  # pragma: no cover - import guard
            from .hotkey import _HAS_WIN32 as has_win32  # type: ignore
        except Exception:  # noqa: BLE001
            has_win32 = False
        win32_available = bool(has_win32)
    if not win32_available:
        return REG_UNAVAILABLE, "Global shortcuts need Windows (pywin32)"
    return "ok", f"Ready · {normalize_hotkey(raw)}"


def registration_status_for(
    action: HotkeyAction,
    *,
    other_actions: list[HotkeyAction],
    reserved_specs: set[str] | frozenset[str],
    win32_available: bool,
    os_registered: bool | None = None,
) -> tuple[str, str]:
    """Compute the live registration status for display.

    ``os_registered`` is the listener's answer for whether the OS accepted the
    key; ``None`` when not yet known (e.g. before the listener starts).
    """
    if not action.enabled:
        return REG_DISABLED, ""
    kind, message = diagnose_action_hotkey(
        action.hotkey,
        self_id=action.id,
        other_actions=other_actions,
        reserved_specs=reserved_specs,
        win32_available=win32_available,
    )
    if kind == REG_INVALID:
        return REG_INVALID, message
    if kind == REG_CONFLICT:
        return REG_CONFLICT, message
    if kind == REG_RESERVED:
        return REG_RESERVED, message
    if kind == REG_UNAVAILABLE:
        return REG_UNAVAILABLE, message
    if os_registered is False:
        return REG_FAILED, "Shortcut unavailable — another app may already use it"
    if os_registered is True:
        return REG_ACTIVE, f"Active · {action.hotkey_display}"
    return REG_UNKNOWN, "Registering…"


STATUS_LABELS: dict[str, str] = {
    REG_ACTIVE: "Active",
    REG_DISABLED: "Disabled",
    REG_FAILED: "Not registered",
    REG_CONFLICT: "Conflict",
    REG_RESERVED: "Reserved",
    REG_INVALID: "Invalid",
    REG_UNAVAILABLE: "Unavailable",
    REG_UNKNOWN: "Unknown",
}


@dataclass(frozen=True)
class CommandActionStatus:
    """Live status for one action — never persisted, recomputed on demand."""

    action: "HotkeyAction"
    status: str
    message: str


def compute_status_rows(
    actions: list[HotkeyAction],
    *,
    reserved_specs: set[str] | frozenset[str],
    win32_available: bool,
    registered_ids: set[int] | frozenset[int] | None = None,
    hotkey_id_by_action: dict[str, int] | None = None,
) -> list[CommandActionStatus]:
    """Compute live registration status for every action in one place.

    Shared by the Hotkey Actions screen and the post-registration refresh so
    the two never drift. ``os_registered`` is derived from the listener's
    accepted-id snapshot; ``None`` when the action has no registerable hotkey.
    """
    registered = registered_ids or set()
    id_by_action = hotkey_id_by_action or {}
    rows: list[CommandActionStatus] = []
    for action in actions:
        hid = id_by_action.get(action.id)
        os_registered: bool | None = None
        if action.enabled and action.hotkey:
            os_registered = hid is not None and hid in registered
        status, message = registration_status_for(
            action, other_actions=actions, reserved_specs=reserved_specs,
            win32_available=win32_available, os_registered=os_registered,
        )
        rows.append(CommandActionStatus(action, status, message))
    return rows


# --- Run log -----------------------------------------------------------------
@dataclass
class RunLogEntry:
    id: str = field(default_factory=models.new_id)
    timestamp: str = field(default_factory=models.now_iso)
    command_id: str = ""
    command_name: str = ""
    action_type: str = ""
    trigger_type: str = "hotkey"
    trigger_value: str = ""
    target: str = ""
    target_label: str = ""
    result: str = RESULT_OK            # ok | failed | blocked
    error: str = ""
    dry_run: bool = False
    clip_ids: list[str] = field(default_factory=list)
    safe_target: str = ""
    proof_hash: str = ""
    app_version: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "RunLogEntry":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})


def default_runlog_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "command_runlog.json"


class CommandRunLog:
    """Lightweight local run log. Useful for trust + debugging, not telemetry."""

    def __init__(self, path: str | os.PathLike | None = None, *, cap: int = 500):
        self._path = Path(path or default_runlog_path())
        self._cap = max(1, cap)

    @property
    def path(self) -> Path:
        return self._path

    def recent(self, limit: int = 100) -> list[RunLogEntry]:
        if not self._path.is_file():
            return []
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except OSError:
            return []
        except json.JSONDecodeError:
            safe_io.quarantine_corrupt(self._path)
            return []
        items = data.get("runs") if isinstance(data, dict) else data
        if not isinstance(items, list):
            return []
        entries = [RunLogEntry.from_dict(e) for e in items if isinstance(e, dict)]
        entries.sort(key=lambda e: e.timestamp, reverse=True)
        return entries[:limit]

    def append(self, entry: RunLogEntry) -> RunLogEntry:
        entries = self.recent(self._cap)
        entries.insert(0, entry)
        entries = entries[: self._cap]
        payload = {"version": 1, "runs": [e.to_dict() for e in entries]}
        safe_io.atomic_write_text(self._path, json.dumps(payload, indent=2))
        return entry

    def clear(self) -> None:
        if self._path.is_file():
            safe_io.atomic_write_text(
                self._path, json.dumps({"version": 1, "runs": []}, indent=2),
            )


# --- Dispatcher --------------------------------------------------------------
@dataclass
class CommandRunResult:
    ok: bool
    result: str
    message: str = ""
    error: str = ""
    entry: Optional[RunLogEntry] = None


class CommandActionDispatcher:
    """Runs a Hotkey Action's handler and records bookkeeping + a run log entry.

    Handlers are supplied by the shell, keyed by action type. A handler may
    return a dict describing the outcome (``ok``, ``error``, ``clip_ids``,
    ``safe_target``, ``proof_hash``, ``message``); returning ``None`` means
    success with no extra detail.
    """

    def __init__(
        self,
        store: HotkeyActionStore,
        runlog: CommandRunLog,
        handlers: dict[str, Callable[[HotkeyAction], Optional[dict]]],
        *,
        is_locked: Callable[[], bool] | None = None,
        confirm: Callable[[HotkeyAction], bool] | None = None,
        app_version: str = "",
        on_event: Callable[[RunLogEntry], None] | None = None,
    ):
        self._store = store
        self._runlog = runlog
        self._handlers = handlers
        self._is_locked = is_locked or (lambda: False)
        self._confirm = confirm
        self._app_version = app_version
        self._on_event = on_event

    def run(
        self,
        action: HotkeyAction,
        *,
        trigger_type: str = "hotkey",
        trigger_value: str = "",
        dry_run: bool = False,
    ) -> CommandRunResult:
        spec = ACTION_SPECS.get(action.action_type)
        tv = trigger_value or action.hotkey

        if not action.enabled:
            # Disabled actions never run; not logged to avoid noise.
            return CommandRunResult(False, RESULT_BLOCKED, message="Command is disabled")

        if spec is None or not spec.implemented:
            return self._record(
                action, RESULT_FAILED, trigger_type, tv, dry_run,
                error="This action is not available yet", live=False,
            )

        if self._is_locked() and not spec.safe_when_locked:
            return self._record(
                action, RESULT_BLOCKED, trigger_type, tv, dry_run,
                message="Vault is locked", error="vault_locked", live=False,
            )

        if not dry_run and (spec.destructive or spec.needs_confirmation):
            if self._confirm is None:
                return self._record(
                    action, RESULT_FAILED, trigger_type, tv, dry_run,
                    message="Confirmation required but no confirmation handler is configured.",
                    error="confirmation_unavailable",
                    live=False,
                )
            if not self._confirm(action):
                return self._record(
                    action, RESULT_BLOCKED, trigger_type, tv, dry_run,
                    message="Cancelled at confirmation", error="cancelled",
                    live=False,
                )

        if dry_run:
            return self._record(
                action, RESULT_OK, trigger_type, tv, dry_run,
                message="Dry run — would run safely", live=False,
            )

        handler = self._handlers.get(action.action_type)
        if handler is None:
            return self._record(
                action, RESULT_FAILED, trigger_type, tv, dry_run,
                error="No handler registered for this action", live=False,
            )

        try:
            outcome = handler(action) or {}
        except Exception as exc:  # noqa: BLE001 - surfaced to the run log
            return self._record(
                action, RESULT_FAILED, trigger_type, tv, dry_run,
                error=str(exc) or exc.__class__.__name__, live=True,
            )

        if isinstance(outcome, dict) and outcome.get("ok") is False:
            return self._record(
                action, RESULT_FAILED, trigger_type, tv, dry_run,
                error=str(outcome.get("error") or "Action reported failure"),
                live=True, outcome=outcome,
            )

        return self._record(
            action, RESULT_OK, trigger_type, tv, dry_run,
            message=str((outcome or {}).get("message") or ""),
            live=True, outcome=outcome if isinstance(outcome, dict) else {},
        )

    def _record(
        self,
        action: HotkeyAction,
        result: str,
        trigger_type: str,
        trigger_value: str,
        dry_run: bool,
        *,
        message: str = "",
        error: str = "",
        live: bool,
        outcome: dict | None = None,
    ) -> CommandRunResult:
        outcome = outcome or {}
        entry = RunLogEntry(
            command_id=action.id,
            command_name=action.name or action_label(action.action_type),
            action_type=action.action_type,
            trigger_type=trigger_type,
            trigger_value=normalize_hotkey(trigger_value) if trigger_value else "",
            target=action.target,
            target_label=action.target_label,
            result=result,
            error=error[:300],
            dry_run=dry_run,
            clip_ids=[str(c) for c in (outcome.get("clip_ids") or [])][:20],
            safe_target=str(outcome.get("safe_target") or ""),
            proof_hash=str(outcome.get("proof_hash") or ""),
            app_version=self._app_version,
        )
        self._runlog.append(entry)
        if self._on_event is not None:
            try:
                self._on_event(entry)
            except Exception:  # noqa: BLE001 - logging must never break a run
                pass

        # Update the action's own stats only for live attempts (not dry runs).
        if live and not dry_run:
            action.last_run_at = entry.timestamp
            action.last_run_failed = result == RESULT_FAILED
            if result == RESULT_OK:
                action.run_count += 1
            self._store.upsert(action)

        return CommandRunResult(
            ok=result == RESULT_OK, result=result, message=message,
            error=error, entry=entry,
        )


# --- Demo fixture ------------------------------------------------------------
def demo_actions(*, macro_id: str = "", macro_label: str = "Email signature",
                 safe_id: str = "default", safe_label: str = "Default Safe") -> list[HotkeyAction]:
    """Representative Hotkey Actions for screenshots and docs.

    Contains only action definitions — never clipboard content or vault history.
    """
    return [
        HotkeyAction(
            id="demo-open-quick-paste", name="Open Quick Paste",
            hotkey="ctrl+alt+v", action_type=ACTION_OPEN_QUICK_PASTE,
        ),
        HotkeyAction(
            id="demo-save-to-safe", name="Save clipboard to Safe",
            hotkey="ctrl+alt+s", action_type=ACTION_SAVE_CLIPBOARD_TO_SAFE,
            target=safe_id, target_label=safe_label,
        ),
        HotkeyAction(
            id="demo-pause-capture", name="Pause / resume capture",
            hotkey="ctrl+alt+d", action_type=ACTION_TOGGLE_CAPTURE,
            run_count=12, last_run_at="2026-06-24T20:42:00",
        ),
        HotkeyAction(
            id="demo-run-macro", name="Run email signature",
            hotkey="ctrl+alt+e", action_type=ACTION_RUN_MACRO,
            target=macro_id, target_label=macro_label, run_count=4,
        ),
        HotkeyAction(
            id="demo-lock-vault", name="Lock vault",
            hotkey="ctrl+alt+l", action_type=ACTION_LOCK_VAULT,
        ),
    ]


def seed_demo_actions(store: HotkeyActionStore, **kw) -> list[HotkeyAction]:
    actions = demo_actions(**kw)
    store.save_all(actions)
    return actions
