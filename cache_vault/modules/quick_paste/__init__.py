"""Quick Paste module manifest.

Wraps the existing Quick Paste settings into a declarative schema.
No files moved; this references ``Settings`` fields directly.
"""

from __future__ import annotations

from .. import ModuleManifest
from ..settings_schema import SettingsCategory, SettingsField


class QuickPasteModule(ModuleManifest):
    """Quick Paste — hotkey-triggered recent-clips picker."""

    @property
    def id(self) -> str:
        return "quick_paste"

    @property
    def name(self) -> str:
        return "Quick Paste"

    @property
    def description(self) -> str:
        return "Hotkey-triggered picker for recent clipboard clips"

    @property
    def category(self) -> str:
        return "command"

    def get_settings_schema(self) -> list[SettingsCategory]:
        return [
            SettingsCategory(
                id="quick_paste", label="Quick Paste", icon="\u238B",
                fields=[
                    SettingsField(
                        "quick_paste_hotkey", "Quick Paste hotkey", "hotkey",
                        "Global hotkey to open the picker",
                        group="Behavior",
                    ),
                    SettingsField(
                        "quick_paste_count", "Items shown", "number",
                        "Number of recent clips in the picker",
                        group="Behavior", min_val=1, max_val=50,
                    ),
                    SettingsField(
                        "auto_paste", "Auto-paste selected clip", "toggle",
                        "Paste the selected item immediately after picking",
                        group="Behavior",
                    ),
                    SettingsField(
                        "restore_clipboard_after_paste",
                        "Restore clipboard after paste", "toggle",
                        "Restore the previous clipboard text after paste delivery",
                        group="Behavior",
                    ),
                ],
            ),
        ]
