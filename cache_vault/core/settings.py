"""Local settings, stored as JSON next to the database.

No network, no telemetry — just a small file under
``%LOCALAPPDATA%\\CacheVault\\settings.json``.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict, field
from pathlib import Path


def default_settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "settings.json"


@dataclass
class Settings:
    capture_paused: bool = False
    # When ON, normal Ctrl+C clipboard changes are saved (unless excluded/blocked).
    auto_capture_enabled: bool = True
    default_safe_id: str = "default"
    manual_save_hotkey: str = "ctrl+shift+c"
    arm_next_copy_hotkey: str = "ctrl+alt+c"
    ignore_next_copy_hotkey: str = "ctrl+shift+x"
    show_safe_picker_on_manual_save: bool = False
    block_sensitive_auto_capture: bool = True
    max_auto_capture_bytes: int = 0  # 0 = unlimited
    user_safes: list[dict] = field(default_factory=list)
    sensitive_expiry_enabled: bool = True   # default ON per doctrine
    sensitive_expiry_minutes: int = 10      # within the doc's 5–15 range
    excluded_apps: list[str] = field(default_factory=list)
    poll_interval_ms: int = 800             # used only by the polling fallback

    # Quick-paste picker (global hotkey).
    quick_paste_hotkey: str = "ctrl+shift+v"  # Win+V is reserved by Windows
    quick_paste_count: int = 12               # how many recent clips to show
    auto_paste: bool = True                   # paste selected item immediately (Ctrl+V to prior app)
    restore_clipboard_after_paste: bool = False  # restore pre-paste clipboard text after delivery

    # Mouse wheel — match Windows Settings scroll lines (SPI_GETWHEELSCROLLLINES).
    use_windows_scroll_settings: bool = True
    scroll_multiplier: float = 1.0            # optional fine-tune; 1.0 = OS-equivalent

    start_with_windows: bool = False          # synced to the HKCU Run key

    # History pruning: keep at most this many live (non-deleted) clips.
    # 0 = unlimited. Favorites always survive pruning.
    history_max_clips: int = 0

    # Cache Vault Mobile — read-only LAN bridge (OFF by default).
    # See docs/MOBILE_ANDROID_DIRECTION.md.
    mobile_access_enabled: bool = False
    mobile_access_port: int = 8742  # LAN read-only API; see MOBILE_ANDROID_DIRECTION.md
    mobile_access_bind_host: str = ""  # empty = use bridge default when enabled
    paired_devices: list[dict] = field(default_factory=list)

    # Vault Macros — saved snippet/macro vault (Macro Safes are not encrypted).
    vault_macros_enabled: bool = True
    vault_macros_setup_completed: bool = False
    default_macro_safe_id: str = "macro-safe"
    macro_menu_hotkey: str = "ctrl+shift+m"
    macro_default_output_mode: str = "clipboard_paste"
    macro_text_shortcuts_enabled: bool = True
    macro_hotkeys_enabled: bool = True
    macro_restore_clipboard_after_paste: bool = False
    macro_sensitive_confirmation: bool = True
    macro_search_content: bool = False
    user_macro_safes: list[dict] = field(default_factory=list)
    macro_starter_safes_initialized: bool = False
    macro_keystroke_enabled: bool = True
    macro_keystroke_delay_ms: int = 10
    macro_keystroke_max_chars: int = 2000

    # First-use guide — shown once until dismissed (Settings can reopen).
    first_use_guide_dismissed: bool = False

    # Vault Lock — local app privacy lock. This is not Safe encryption.
    vault_lock_enabled: bool = False
    vault_lock_mode: str = "pin"  # "pin" or "passphrase"
    vault_lock_salt: str = ""
    vault_lock_hash: str = ""
    vault_lock_iterations: int = 200_000
    vault_lock_on_startup: bool = False
    vault_lock_when_minimized: bool = False
    vault_lock_auto_minutes: int = 0  # 0 = disabled
    vault_lock_style: str = "teal_classic"
    vault_lock_accent: str = "#1A9E8C"
    vault_lock_reduced_motion: bool = True
    vault_lock_show_local_only: bool = True
    sidebar_collapsed_sections: list[str] = field(default_factory=list)

    # --- persistence ---
    @classmethod
    def load(cls, path: str | os.PathLike | None = None) -> "Settings":
        path = Path(path or default_settings_path())
        if not path.exists():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return cls()
        known = {f for f in cls().__dict__}
        s = cls(**{k: v for k, v in data.items() if k in known})
        try:
            s.history_max_clips = max(0, int(s.history_max_clips))
        except (TypeError, ValueError):
            s.history_max_clips = 0
        try:
            s.mobile_access_port = max(1024, min(65535, int(s.mobile_access_port)))
        except (TypeError, ValueError):
            s.mobile_access_port = 8742
        if not isinstance(s.paired_devices, list):
            s.paired_devices = []
        if not isinstance(s.user_safes, list):
            s.user_safes = []
        if not isinstance(s.user_macro_safes, list):
            s.user_macro_safes = []
        s.vault_macros_enabled = bool(s.vault_macros_enabled)
        s.vault_macros_setup_completed = bool(s.vault_macros_setup_completed)
        s.macro_text_shortcuts_enabled = bool(s.macro_text_shortcuts_enabled)
        s.macro_hotkeys_enabled = bool(s.macro_hotkeys_enabled)
        s.macro_restore_clipboard_after_paste = bool(s.macro_restore_clipboard_after_paste)
        s.macro_sensitive_confirmation = bool(s.macro_sensitive_confirmation)
        s.macro_search_content = bool(s.macro_search_content)
        s.macro_starter_safes_initialized = bool(getattr(s, "macro_starter_safes_initialized", False))
        s.macro_keystroke_enabled = bool(getattr(s, "macro_keystroke_enabled", True))
        try:
            s.macro_keystroke_delay_ms = max(1, min(100, int(getattr(s, "macro_keystroke_delay_ms", 10))))
        except (TypeError, ValueError):
            s.macro_keystroke_delay_ms = 10
        try:
            s.macro_keystroke_max_chars = max(100, min(10000, int(getattr(s, "macro_keystroke_max_chars", 2000))))
        except (TypeError, ValueError):
            s.macro_keystroke_max_chars = 2000
        if not (s.default_macro_safe_id or "").strip():
            s.default_macro_safe_id = "macro-safe"
        if s.macro_default_output_mode not in ("clipboard_paste", "keystroke"):
            s.macro_default_output_mode = "clipboard_paste"
        try:
            s.max_auto_capture_bytes = max(0, int(s.max_auto_capture_bytes))
        except (TypeError, ValueError):
            s.max_auto_capture_bytes = 0
        s.auto_capture_enabled = bool(s.auto_capture_enabled)
        s.block_sensitive_auto_capture = bool(s.block_sensitive_auto_capture)
        s.show_safe_picker_on_manual_save = bool(s.show_safe_picker_on_manual_save)
        if not (s.default_safe_id or "").strip():
            s.default_safe_id = "default"
        try:
            s.scroll_multiplier = max(0.25, min(4.0, float(s.scroll_multiplier)))
        except (TypeError, ValueError):
            s.scroll_multiplier = 1.0
        s.restore_clipboard_after_paste = bool(s.restore_clipboard_after_paste)
        s.first_use_guide_dismissed = bool(getattr(s, "first_use_guide_dismissed", False))
        s.vault_lock_enabled = bool(getattr(s, "vault_lock_enabled", False))
        if getattr(s, "vault_lock_mode", "pin") not in ("pin", "passphrase"):
            s.vault_lock_mode = "pin"
        s.vault_lock_salt = str(getattr(s, "vault_lock_salt", "") or "")
        s.vault_lock_hash = str(getattr(s, "vault_lock_hash", "") or "")
        try:
            s.vault_lock_iterations = max(
                1, int(getattr(s, "vault_lock_iterations", 200_000)))
        except (TypeError, ValueError):
            s.vault_lock_iterations = 200_000
        s.vault_lock_on_startup = bool(getattr(s, "vault_lock_on_startup", False))
        s.vault_lock_when_minimized = bool(getattr(s, "vault_lock_when_minimized", False))
        try:
            s.vault_lock_auto_minutes = max(
                0, min(1440, int(getattr(s, "vault_lock_auto_minutes", 0))))
        except (TypeError, ValueError):
            s.vault_lock_auto_minutes = 0
        if getattr(s, "vault_lock_style", "teal_classic") not in (
            "vault_door",
            "minimal_seal",
            "keypad",
            "passphrase",
            "graphite",
            "teal_classic",
        ):
            s.vault_lock_style = "teal_classic"
        s.vault_lock_accent = str(getattr(s, "vault_lock_accent", "#1A9E8C") or "#1A9E8C")
        s.vault_lock_reduced_motion = bool(getattr(s, "vault_lock_reduced_motion", True))
        s.vault_lock_show_local_only = bool(getattr(s, "vault_lock_show_local_only", True))
        if not isinstance(getattr(s, "sidebar_collapsed_sections", []), list):
            s.sidebar_collapsed_sections = []
        s._persist_path = path
        return s

    def save(self, path: str | os.PathLike | None = None) -> None:
        path = Path(path or getattr(self, "_persist_path", None) or default_settings_path())
        self._persist_path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def is_app_excluded(self, app_name: str | None) -> bool:
        if not app_name:
            return False
        low = app_name.lower()
        return any(low == ex.lower() or ex.lower() in low
                   for ex in self.excluded_apps)
