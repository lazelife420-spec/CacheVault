"""Vault Macro execution engine — hotkeys, shortcuts, paste/type delivery.

Core-only: no CustomTkinter imports.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from . import models
from .macro_receipts import record_macro_execution_receipt
from .macro_variables import MacroVariableContext, expand_macro_variables
from .paste_delivery import (
    PasteResult,
    deliver_ctrl_v,
    deliver_text_keystrokes,
    restore_clipboard_text,
    send_backspaces,
    set_clipboard_text,
    snapshot_clipboard_text,
    window_title,
)
from .sensitive import detect as detect_sensitive
from .vault_macros import (
    OUTPUT_CLIPBOARD_PASTE,
    OUTPUT_KEYSTROKE,
    RESERVED_HOTKEYS,
    TRIGGER_HOTKEY,
    TRIGGER_MENU_ONLY,
    TRIGGER_TEXT_SHORTCUT,
    Macro,
    MacroSafeRegistry,
    MacroStore,
    normalize_hotkey,
)

NoticeFn = Callable[[str], None]


@dataclass
class ExecuteResult:
    ok: bool
    reason: str = ""
    macro_id: str | None = None
    macro_name: str = ""
    trigger_type: str = ""
    trigger_value: str = ""
    output_mode: str = OUTPUT_CLIPBOARD_PASTE
    target_title: str = ""
    clipboard_restored: bool = False
    expanded_hash: str | None = None
    picker_needed: bool = False
    blocked_sensitive: bool = False
    skipped_disabled: bool = False
    action: str = "macro_executed"


def system_reserved_hotkeys(settings) -> set[str]:
    """Hotkeys reserved by Cache Vault capture/paste/macro menu."""
    specs = [
        getattr(settings, "quick_paste_hotkey", "ctrl+shift+v"),
        getattr(settings, "manual_save_hotkey", "ctrl+shift+c"),
        getattr(settings, "arm_next_copy_hotkey", "ctrl+alt+c"),
        getattr(settings, "ignore_next_copy_hotkey", "ctrl+shift+x"),
        getattr(settings, "macro_menu_hotkey", "ctrl+shift+m"),
    ]
    return {normalize_hotkey(s) for s in specs if s} | RESERVED_HOTKEYS


def find_macros_for_hotkey(macros: list[Macro], hotkey: str) -> list[Macro]:
    spec = normalize_hotkey(hotkey)
    if not spec:
        return []
    return [
        m for m in macros
        if m.enabled
        and m.trigger_type == TRIGGER_HOTKEY
        and normalize_hotkey(m.trigger_value) == spec
    ]


def find_macro_for_shortcut(macros: list[Macro], shortcut: str) -> Macro | None:
    sc = (shortcut or "").strip()
    if not sc:
        return None
    matches = [
        m for m in macros
        if m.enabled
        and m.trigger_type == TRIGGER_TEXT_SHORTCUT
        and (m.trigger_value or "").strip() == sc
    ]
    return matches[0] if len(matches) == 1 else None


def match_shortcut_suffix(buffer: str, macros: list[Macro]) -> tuple[str, Macro] | None:
    """Return (shortcut, macro) when buffer ends with a configured shortcut."""
    buf = buffer or ""
    best: tuple[str, Macro] | None = None
    for m in macros:
        if not m.enabled or m.trigger_type != TRIGGER_TEXT_SHORTCUT:
            continue
        sc = (m.trigger_value or "").strip()
        if sc and buf.endswith(sc):
            if best is None or len(sc) > len(best[0]):
                best = (sc, m)
    return best


class MacroExecutor:
    """Resolve, expand, deliver, and receipt Vault Macro runs."""

    def __init__(
        self,
        settings,
        store: MacroStore,
        registry: MacroSafeRegistry,
        events,
        *,
        on_notice: NoticeFn | None = None,
        confirm_sensitive: Callable[[str], bool] | None = None,
        clipboard_writer=None,
    ):
        self.settings = settings
        self.store = store
        self.registry = registry
        self.events = events
        self.on_notice = on_notice
        self.confirm_sensitive = confirm_sensitive
        # Slice A custody: when the composition root provides the shared
        # ClipboardWriter, macro clipboard output/restore is registered so the
        # monitor never recaptures it. None preserves the legacy direct calls.
        self._clipboard_writer = clipboard_writer

    def _notice(self, msg: str) -> None:
        if self.on_notice:
            self.on_notice(msg)

    def execution_allowed(self) -> tuple[bool, str]:
        if not getattr(self.settings, "vault_macros_enabled", True):
            return False, "vault_macros_disabled"
        if not getattr(self.settings, "vault_macros_setup_completed", False):
            return False, "setup_incomplete"
        return True, ""

    def can_execute_macro(self, macro: Macro) -> tuple[bool, str]:
        ok, reason = self.execution_allowed()
        if not ok:
            return False, reason
        if not macro.enabled:
            return False, "macro_disabled"
        if not (macro.body or "").strip() and macro.output_mode == OUTPUT_CLIPBOARD_PASTE:
            return False, "empty_body"
        return True, ""

    def prepare_output(
        self,
        macro: Macro,
        *,
        item_id: str = "",
    ) -> tuple[str, list[str], ExecuteResult | None]:
        safe = self.registry.resolve(macro.safe_id)
        ctx = MacroVariableContext(
            safe_name=safe.name if safe else "",
            item_id=item_id or macro.id,
        )
        expanded, missing = expand_macro_variables(macro.body or "", ctx)
        if missing:
            return expanded, missing, ExecuteResult(
                ok=False,
                reason=f"missing_variables:{','.join(missing)}",
                macro_id=macro.id,
                macro_name=macro.name,
                action="macro_failed",
            )
        sens = detect_sensitive(expanded)
        if sens.is_sensitive or (macro.sensitive_confirm and detect_sensitive(macro.body or "").is_sensitive):
            if getattr(self.settings, "macro_sensitive_confirmation", True):
                if self.confirm_sensitive and not self.confirm_sensitive(macro.name):
                    return expanded, missing, ExecuteResult(
                        ok=False,
                        reason="sensitive_blocked",
                        macro_id=macro.id,
                        macro_name=macro.name,
                        blocked_sensitive=True,
                        action="macro_blocked_sensitive",
                    )
        clip_sens = detect_sensitive(ctx.clipboard_text or "") if ctx.clipboard_text else None
        if (
            "{clipboard}" in (macro.body or "")
            and clip_sens
            and clip_sens.is_sensitive
            and getattr(self.settings, "macro_sensitive_confirmation", True)
        ):
            if self.confirm_sensitive and not self.confirm_sensitive(f"{macro.name} (clipboard)"):
                return expanded, missing, ExecuteResult(
                    ok=False,
                    reason="sensitive_clipboard_blocked",
                    macro_id=macro.id,
                    macro_name=macro.name,
                    blocked_sensitive=True,
                    action="macro_blocked_sensitive",
                )
        return expanded, missing, None

    def execute(
        self,
        macro: Macro,
        *,
        trigger_type: str,
        trigger_value: str = "",
        target_hwnd=None,
        shortcut_backspaces: int = 0,
    ) -> ExecuteResult:
        can, reason = self.can_execute_macro(macro)
        if not can:
            if reason == "macro_disabled":
                self._record(macro, trigger_type, trigger_value, ExecuteResult(
                    ok=False, reason=reason, macro_id=macro.id, macro_name=macro.name,
                    skipped_disabled=True, action="macro_disabled_skipped",
                ))
            return ExecuteResult(
                ok=False, reason=reason, macro_id=macro.id, macro_name=macro.name,
                skipped_disabled=reason == "macro_disabled",
            )

        expanded, _missing, prep_fail = self.prepare_output(macro)
        if prep_fail:
            self._record(macro, trigger_type, trigger_value, prep_fail)
            self._notice("Macro blocked or failed — see receipts.")
            return prep_fail

        output_mode = macro.output_mode or getattr(
            self.settings, "macro_default_output_mode", OUTPUT_CLIPBOARD_PASTE,
        )
        expanded_hash = models.content_hash(expanded)

        if shortcut_backspaces > 0 and target_hwnd:
            send_backspaces(target_hwnd, shortcut_backspaces)

        prior_clipboard = None
        restore = bool(getattr(self.settings, "macro_restore_clipboard_after_paste", False))
        if output_mode == OUTPUT_CLIPBOARD_PASTE and restore:
            prior_clipboard = snapshot_clipboard_text()

        if output_mode == OUTPUT_CLIPBOARD_PASTE:
            if self._clipboard_writer is not None:
                wrote_clipboard = self._clipboard_writer.write_text(expanded, operation="macro_output")
            else:
                wrote_clipboard = set_clipboard_text(expanded)
            if not wrote_clipboard:
                result = ExecuteResult(
                    ok=False, reason="clipboard_set_failed",
                    macro_id=macro.id, macro_name=macro.name,
                    trigger_type=trigger_type, trigger_value=trigger_value,
                    output_mode=output_mode, expanded_hash=expanded_hash,
                    action="macro_failed",
                )
                self._record(macro, trigger_type, trigger_value, result)
                self._update_macro_after_run(macro, success=False)
                return result
            if target_hwnd:
                paste = deliver_ctrl_v(target_hwnd)
            else:
                paste = PasteResult(True, "clipboard_only", "")
            clipboard_restored = False
            if target_hwnd and paste.ok and restore:
                time.sleep(0.12)
                if self._clipboard_writer is not None:
                    clipboard_restored = self._clipboard_writer.restore_text(
                        prior_clipboard, operation="macro_restore",
                    )
                else:
                    clipboard_restored = restore_clipboard_text(prior_clipboard)
        elif output_mode == OUTPUT_KEYSTROKE:
            if not getattr(self.settings, "macro_keystroke_enabled", True):
                result = ExecuteResult(
                    ok=False, reason="keystroke_mode_disabled",
                    macro_id=macro.id, macro_name=macro.name,
                    trigger_type=trigger_type, trigger_value=trigger_value,
                    output_mode=output_mode, action="macro_failed",
                )
                self._record(macro, trigger_type, trigger_value, result)
                return result
            max_chars = int(getattr(self.settings, "macro_keystroke_max_chars", 2000) or 2000)
            if len(expanded) > max_chars:
                result = ExecuteResult(
                    ok=False, reason="keystroke_too_large",
                    macro_id=macro.id, macro_name=macro.name,
                    trigger_type=trigger_type, trigger_value=trigger_value,
                    output_mode=output_mode, action="macro_failed",
                )
                self._record(macro, trigger_type, trigger_value, result)
                self._notice("Macro too large for keystroke mode.")
                return result
            delay = float(getattr(self.settings, "macro_keystroke_delay_ms", 10) or 10) / 1000.0
            paste = deliver_text_keystrokes(target_hwnd, expanded, delay_s=delay)
            clipboard_restored = False
        else:
            result = ExecuteResult(
                ok=False, reason="invalid_output_mode",
                macro_id=macro.id, macro_name=macro.name,
                action="macro_failed",
            )
            self._record(macro, trigger_type, trigger_value, result)
            return result

        action = {
            TRIGGER_HOTKEY: "macro_hotkey_executed",
            TRIGGER_TEXT_SHORTCUT: "text_shortcut_expanded",
            TRIGGER_MENU_ONLY: "macro_picker_executed",
        }.get(trigger_type, "macro_executed")

        result = ExecuteResult(
            ok=paste.ok,
            reason=paste.reason or ("ok" if paste.ok else "delivery_failed"),
            macro_id=macro.id,
            macro_name=macro.name,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            output_mode=output_mode,
            target_title=paste.target_title or window_title(target_hwnd),
            clipboard_restored=clipboard_restored,
            expanded_hash=expanded_hash,
            action=action if paste.ok else "macro_failed",
        )
        self._record(macro, trigger_type, trigger_value, result)
        self._update_macro_after_run(macro, success=paste.ok)
        if not paste.ok:
            self._notice(f"Macro failed: {result.reason}")
        return result

    def execute_by_id(
        self,
        macro_id: str,
        *,
        trigger_type: str = TRIGGER_MENU_ONLY,
        trigger_value: str = "",
        target_hwnd=None,
        shortcut_backspaces: int = 0,
    ) -> ExecuteResult:
        macro = self.store.get(macro_id)
        if macro is None:
            return ExecuteResult(ok=False, reason="macro_not_found", macro_id=macro_id, action="macro_failed")
        return self.execute(
            macro,
            trigger_type=trigger_type,
            trigger_value=trigger_value,
            target_hwnd=target_hwnd,
            shortcut_backspaces=shortcut_backspaces,
        )

    def resolve_hotkey(self, hotkey: str) -> tuple[list[Macro], bool]:
        """Return matching enabled macros and whether picker is needed."""
        if not getattr(self.settings, "macro_hotkeys_enabled", True):
            return [], False
        macros = find_macros_for_hotkey(self.store.load_all(), hotkey)
        return macros, len(macros) > 1

    def _update_macro_after_run(self, macro: Macro, *, success: bool) -> None:
        macro.run_count = int(macro.run_count or 0) + 1
        macro.receipt_count = int(macro.receipt_count or 0) + 1
        macro.last_used_at = models.now_iso()
        macro.last_run_failed = not success
        self.store.upsert(macro)

    def _record(
        self,
        macro: Macro,
        trigger_type: str,
        trigger_value: str,
        result: ExecuteResult,
    ) -> None:
        safe = self.registry.resolve(macro.safe_id)
        record_macro_execution_receipt(
            self.events,
            action=result.action,
            event_type=result.action,
            success=result.ok,
            macro_id=macro.id,
            macro_name=macro.name,
            safe_id=macro.safe_id,
            safe_name=safe.name if safe else None,
            smart_type=macro.smart_type,
            trigger_type=trigger_type or result.trigger_type,
            trigger_value=trigger_value or result.trigger_value,
            output_mode=result.output_mode,
            target_title=result.target_title,
            content_hash=result.expanded_hash,
            clipboard_restored=result.clipboard_restored,
            warning=result.reason if result.blocked_sensitive else None,
            error=None if result.ok else result.reason,
        )
