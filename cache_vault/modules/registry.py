"""Module registry — explicit registration, search, and health reporting.

``build_default_registry()`` wires up the four foundation modules plus the
global (non-module-owned) settings categories.
"""

from __future__ import annotations

from .settings_schema import SettingsCategory, SettingsField, StatusRow
from . import ModuleManifest


class ModuleRegistry:
    """Holds registered modules and the global settings categories."""

    def __init__(self) -> None:
        self._modules: dict[str, ModuleManifest] = {}
        self._global_categories: list[SettingsCategory] = []
        self._category_order: list[str] = []

    # --- registration ---

    def register(self, manifest: ModuleManifest) -> None:
        if manifest.id in self._modules:
            raise ValueError(f"Duplicate module id: '{manifest.id}'")
        self._modules[manifest.id] = manifest

    def register_global_category(self, category: SettingsCategory) -> None:
        self._global_categories.append(category)

    def set_category_order(self, order: list[str]) -> None:
        self._category_order = list(order)

    # --- queries ---

    def get(self, module_id: str) -> ModuleManifest | None:
        return self._modules.get(module_id)

    def all(self) -> list[ModuleManifest]:
        return list(self._modules.values())

    def settings_categories(self) -> list[SettingsCategory]:
        """Global categories first (in display order), then per-module."""
        ordered: list[SettingsCategory] = []
        order_ids = self._category_order or [c.id for c in self._global_categories]

        # Global categories in fixed order.
        by_id = {c.id: c for c in self._global_categories}
        for cid in order_ids:
            if cid in by_id:
                ordered.append(by_id[cid])
        # Any global categories not in the explicit order (safety net).
        for c in self._global_categories:
            if c not in ordered:
                ordered.append(c)

        # Module categories.
        for mod in self._modules.values():
            ordered.extend(mod.get_settings_schema())
        return ordered

    def search_settings(self, query: str) -> list[tuple[str, SettingsField]]:
        """Case-insensitive substring match across label, description, key.

        Returns ``(category_label, field)`` pairs.  Empty query → empty list.
        """
        if not query:
            return []
        q = query.lower()
        results: list[tuple[str, SettingsField]] = []
        for cat in self.settings_categories():
            for sf in cat.fields:
                if (q in sf.label.lower()
                        or q in sf.description.lower()
                        or q in sf.key.lower()):
                    results.append((cat.label, sf))
        return results

    def health_report(self) -> dict[str, dict]:
        return {mod.id: mod.run_health_check() for mod in self._modules.values()}


# ---------------------------------------------------------------------------
# Global (non-module) settings categories
# ---------------------------------------------------------------------------

_GLOBAL_CATEGORIES: list[SettingsCategory] = [
    SettingsCategory(
        id="general", label="General", icon="\u2699",
        fields=[
            SettingsField("start_with_windows", "Start with Windows",
                          "toggle", "Launch Cache Vault when Windows starts"),
        ],
    ),
    SettingsCategory(
        id="capture", label="Capture", icon="\u25C9",
        fields=[
            SettingsField("capture_paused", "Pause capture", "toggle",
                          "Pause all clipboard capture"),
            SettingsField("auto_capture_enabled", "Auto-capture", "toggle",
                          "Save normal clipboard copies automatically"),
            SettingsField("block_sensitive_auto_capture",
                          "Block sensitive auto-capture", "toggle",
                          "Do not auto-capture sensitive-looking clips"),
            SettingsField("max_auto_capture_bytes", "Max auto-capture size",
                          "number",
                          "Maximum bytes for auto-captured clips (0 = unlimited)",
                          min_val=0),
            SettingsField("default_safe_id", "Default Safe", "text",
                          "Default Safe for new clips"),
            SettingsField("show_safe_picker_on_manual_save",
                          "Show Safe picker on manual save", "toggle",
                          "Prompt for a Safe when saving manually"),
            SettingsField("excluded_apps", "Excluded apps", "text",
                          "Apps excluded from auto-capture (one per line)"),
        ],
    ),
    SettingsCategory(
        id="shortcuts", label="Keyboard Shortcuts", icon="\u2328",
        fields=[
            SettingsField("manual_save_hotkey", "Save to Vault", "hotkey",
                          "Save the current clipboard now"),
            SettingsField("arm_next_copy_hotkey", "Save next copy", "hotkey",
                          "Arm: save only the next Ctrl+C copy"),
            SettingsField("ignore_next_copy_hotkey", "Skip capture", "hotkey",
                          "Ignore the next clipboard copy (one shot)"),
            SettingsField("quick_paste_hotkey", "Quick Paste menu", "hotkey",
                          "Open the recent-clips picker anywhere"),
            SettingsField("macro_menu_hotkey", "Macro menu", "hotkey",
                          "Open the Snippet Macros picker"),
        ],
    ),
    SettingsCategory(
        id="macros", label="Snippet Macros", icon="\u26A1",
        fields=[
            SettingsField("vault_macros_enabled", "Enable Snippet Macros", "toggle",
                          "Master switch for macros"),
            SettingsField("macro_text_shortcuts_enabled", "Text shortcuts", "toggle",
                          "Enable text shortcut expansion"),
            SettingsField("macro_hotkeys_enabled", "Macro hotkeys", "toggle",
                          "Enable per-macro hotkey triggers"),
            SettingsField("macro_restore_clipboard_after_paste",
                          "Restore clipboard after macro paste", "toggle",
                          "Restore previous clipboard after a macro paste"),
            SettingsField("macro_sensitive_confirmation",
                          "Sensitive macro confirmation", "toggle",
                          "Require confirmation for sensitive-looking macros"),
            SettingsField("macro_keystroke_enabled", "Keystroke output", "toggle",
                          "Allow keystroke output mode (slower, ASCII-focused)"),
            SettingsField("macro_keystroke_delay_ms", "Keystroke delay (ms)", "number",
                          "Delay between keystrokes in keystroke mode",
                          min_val=1, max_val=100),
            SettingsField("macro_keystroke_max_chars", "Max keystroke chars", "number",
                          "Maximum characters for keystroke output",
                          min_val=100, max_val=10000),
            SettingsField("macro_default_output_mode", "Default output mode", "choice",
                          "Default delivery method for macros",
                          choices=["clipboard_paste", "keystroke"]),
            SettingsField("macro_search_content", "Search macro content", "toggle",
                          "Include macro body text in search results"),
        ],
    ),
    SettingsCategory(
        id="display", label="Display", icon="\u25A6",
        fields=[
            SettingsField("use_windows_scroll_settings",
                          "Use Windows scroll settings", "toggle",
                          "Scroll speed follows Windows mouse wheel lines"),
            SettingsField("scroll_multiplier", "Scroll multiplier", "number",
                          "Fine-tune scroll speed (1.0 = OS default)",
                          min_val=0.25, max_val=4.0),
        ],
    ),
    SettingsCategory(
        id="vault_lock", label="Vault Lock", icon="\U0001F512",
        fields=[
            SettingsField("vault_lock_enabled", "Enable Vault Lock", "toggle",
                          "App privacy lock for the local UI"),
            SettingsField("vault_lock_mode", "Lock mode", "choice",
                          "PIN or passphrase", choices=["pin", "passphrase"]),
            SettingsField("vault_lock_on_startup", "Lock on startup", "toggle",
                          "Require unlock when Cache Vault starts"),
            SettingsField("vault_lock_when_minimized", "Lock when minimized", "toggle",
                          "Lock when the window is minimized"),
            SettingsField("vault_lock_auto_minutes", "Auto-lock minutes", "number",
                          "Lock after this many idle minutes (0 = off)",
                          min_val=0, max_val=1440),
            SettingsField("vault_lock_style", "Lock style", "choice",
                          "Visual style for the lock screen",
                          choices=[
                              "vault_door", "minimal_seal", "keypad",
                              "passphrase", "graphite", "teal_classic",
                          ]),
            SettingsField("vault_lock_accent", "Lock accent color", "text",
                          "Hex color for the lock screen accent"),
            SettingsField("vault_lock_reduced_motion", "Reduced motion", "toggle",
                          "Reduce lock screen animations"),
            SettingsField("vault_lock_show_local_only",
                          "Show 'Vault sealed \u00b7 Local-first'", "toggle",
                          "Display the local-first seal on the lock screen"),
        ],
    ),
    SettingsCategory(
        id="history", label="History", icon="\u23F1",
        fields=[
            SettingsField("history_max_clips", "History limit", "number",
                          "Maximum live clips (0 = unlimited, favorites survive pruning)",
                          min_val=0),
        ],
    ),
]

# Fixed display order for settings sidebar.
_CATEGORY_ORDER = [
    "general", "capture", "shortcuts",
    # Module categories interleave here by registration order:
    "quick_paste",
    "macros",
    # Module:
    "mobile_bridge",
    # Module:
    "proof",
    "display",
    # Module:
    "image_viewer",
    "vault_lock", "history",
]


def build_default_registry() -> ModuleRegistry:
    """Create the registry with global categories and the four foundation modules."""
    from .mobile_bridge import MobileBridgeModule
    from .image_viewer import ImageViewerModule
    from .quick_paste import QuickPasteModule
    from .proof import ProofModule

    reg = ModuleRegistry()

    for cat in _GLOBAL_CATEGORIES:
        reg.register_global_category(cat)
    reg.set_category_order(_CATEGORY_ORDER)

    reg.register(MobileBridgeModule())
    reg.register(ImageViewerModule())
    reg.register(QuickPasteModule())
    reg.register(ProofModule())

    return reg
