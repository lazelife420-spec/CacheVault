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


def _run_contained_selftest() -> int:
    """Run selftest inside an automatically managed, isolated temporary profile root."""
    import os
    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="cachevault-selftest-")
    orig_env = {
        k: os.environ.get(k)
        for k in ("LOCALAPPDATA", "TEMP", "TMP", "USERPROFILE", "CACHE_VAULT_DISABLE_TRAY")
    }

    try:
        os.environ["LOCALAPPDATA"] = temp_dir
        os.environ["TEMP"] = temp_dir
        os.environ["TMP"] = temp_dir
        os.environ["USERPROFILE"] = temp_dir
        os.environ["CACHE_VAULT_DISABLE_TRAY"] = "1"

        res = _selftest()
    except Exception as exc:
        sys.stderr.write(f"image_viewer selftest execution error: {exc}\n")
        sys.stderr.flush()
        res = 1
    finally:
        for k, v in orig_env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

        if os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=False)
            except Exception as cleanup_exc:
                sys.stderr.write(f"selftest cleanup failed for '{temp_dir}': {cleanup_exc}\n")
                sys.stderr.flush()
                res = 1
    return res


def main() -> int:
    if "--selftest" in sys.argv:
        return _run_contained_selftest()

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
