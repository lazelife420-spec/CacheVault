"""Image Viewer module manifest.

Placeholder module — no image-specific settings exist on the ``Settings``
dataclass yet.  Standalone launcher and gallery UI come in Chunk B.
"""

from __future__ import annotations

from .. import ModuleManifest
from ..settings_schema import SettingsCategory


class ImageViewerModule(ModuleManifest):
    """Images — screenshot and image clip gallery."""

    @property
    def id(self) -> str:
        return "image_viewer"

    @property
    def name(self) -> str:
        return "Images"

    @property
    def description(self) -> str:
        return "Screenshot and image clip gallery viewer"

    @property
    def category(self) -> str:
        return "vault"

    def get_settings_schema(self) -> list[SettingsCategory]:
        return []

    def run_health_check(self) -> dict:
        return {"status": "ok"}
