"""Standalone Image Viewer launcher.

Usage:
    python -m cache_vault.modules.image_viewer           # launch image gallery (stub)
    python -m cache_vault.modules.image_viewer --selftest # headless sanity check
"""

from __future__ import annotations

import sys


def _selftest() -> int:
    """Headless sanity check for Image Viewer module."""
    try:
        from cache_vault.core.image_assets import assets_dir
        from cache_vault.modules.image_viewer import ImageViewerModule

        # Test manifest properties
        module = ImageViewerModule()
        assert module.id == "image_viewer"
        assert "Images" in module.name

        # Test assets directory access (read-only check)
        path = assets_dir()
        assert path.exists()

        # Test module health check
        health = module.run_health_check()
        assert health["status"] == "ok"

        print("image_viewer selftest OK")
        return 0
    except Exception as exc:
        print(f"image_viewer selftest FAILED: {exc}")
        return 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    print("Cache Vault Image Viewer")
    print("------------------------")
    print("Storage path:", end=" ")
    try:
        from cache_vault.core.image_assets import assets_dir
        print(assets_dir())
    except Exception:
        print("Unknown")

    print("\n[UI Stub] The standalone gallery UI will be implemented in a future update.")
    print("Currently, this launcher verifies storage access and module integrity.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
