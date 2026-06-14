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
    sensitive_expiry_enabled: bool = True   # default ON per doctrine
    sensitive_expiry_minutes: int = 10      # within the doc's 5–15 range
    excluded_apps: list[str] = field(default_factory=list)
    poll_interval_ms: int = 800             # used only by the polling fallback

    # Quick-paste picker (global hotkey).
    quick_paste_hotkey: str = "ctrl+shift+v"  # Win+V is reserved by Windows
    quick_paste_count: int = 12               # how many recent clips to show
    auto_paste: bool = True                   # send Ctrl+V after choosing

    start_with_windows: bool = False          # synced to the HKCU Run key

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
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: str | os.PathLike | None = None) -> None:
        path = Path(path or default_settings_path())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    def is_app_excluded(self, app_name: str | None) -> bool:
        if not app_name:
            return False
        low = app_name.lower()
        return any(low == ex.lower() or ex.lower() in low
                   for ex in self.excluded_apps)
