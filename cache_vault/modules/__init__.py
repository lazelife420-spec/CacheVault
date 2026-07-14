"""Module manifest contract for Cache Vault features.

Each major feature registers a ModuleManifest that declares its identity,
settings schema, status indicators, and health-check logic.  The desktop
shell composes registered modules; individual modules can also launch
standalone (when implemented in a future chunk).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .settings_schema import SettingsCategory, StatusRow


class ModuleManifest(ABC):
    """Base contract every Cache Vault module must satisfy."""

    # --- identity (abstract) ---

    @property
    @abstractmethod
    def id(self) -> str:
        """Unique module identifier, e.g. ``'mobile_bridge'``."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable display name."""

    @property
    @abstractmethod
    def description(self) -> str:
        """One-line description of the module's purpose."""

    # --- optional overrides with sane defaults ---

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def category(self) -> str:
        """Settings sidebar category bucket."""
        return "general"

    @property
    def dependencies(self) -> list[str]:
        """Other module *ids* this module requires."""
        return []

    # --- settings / status ---

    def get_settings_schema(self) -> list[SettingsCategory]:
        """Declarative list of settings categories this module owns."""
        return []

    def get_status_rows(self) -> list[StatusRow]:
        """Live status indicators shown in the settings panel."""
        return []

    # --- lifecycle ---

    def launch_standalone(self) -> None:
        """Open a standalone window for this module."""
        raise NotImplementedError(f"{self.name} does not support standalone mode yet")

    def mount_in_shell(self, parent: object) -> None:
        """Embed this module's UI into the desktop shell."""
        raise NotImplementedError(f"{self.name} does not support embedded mode yet")

    # --- diagnostics ---

    def run_health_check(self) -> dict:
        """Return ``{"status": "ok"|"warning"|"error", ...}``."""
        return {"status": "ok"}

    def export_receipt(self) -> dict | None:
        """Return a proof receipt dict, or *None* if not applicable."""
        return None
