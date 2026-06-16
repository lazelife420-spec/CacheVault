"""Cache Vault™ — application entry point.

    python app.py            # launch the desktop app
    python app.py --selftest # headless sanity check (no window, for CI)
"""

from __future__ import annotations

import sys


def _selftest() -> int:
    """Exercise the core pipeline without a display — used by CI smoke checks."""
    from io import BytesIO

    from PIL import Image

    from cache_vault.core.mobile.bridge import MobileBridge
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    vault.capture("https://example.com", source_app="test")
    vault.capture("git status", source_app="test")
    secret = vault.capture("sk-abc123DEF456ghi789JKL0", source_app="test")
    assert secret is not None and secret.is_sensitive
    assert len(vault.list_clips()) == 3

    buf = BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, format="PNG")
    png = buf.getvalue()
    img = vault.capture_image(png, width=4, height=4, source_app="test")
    assert img is not None
    assert vault.storage.has_clip_asset(img.id)

    bridge = MobileBridge(vault)
    assert bridge.allowed_routes()  # mobile stack importable in frozen builds

    vault.clear_sensitive()
    vault.close()
    print("selftest OK — core capture/classify/sensitive/image/mobile pipeline works")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    from cache_vault.core.settings import Settings
    from cache_vault.ui.scroll_patch import install_windows_scroll_patch, scroll_config_from_settings

    _settings = Settings.load()
    install_windows_scroll_patch(lambda: scroll_config_from_settings(_settings))

    from cache_vault.core.single_instance import claim_or_exit
    claim_or_exit()

    try:
        import customtkinter as ctk
    except ImportError:
        sys.stderr.write(
            "customtkinter is not installed.\n"
            "Install dependencies first:  pip install -r requirements.txt\n"
        )
        return 1

    from cache_vault.ui.crashlog import install_global_hook
    from cache_vault.ui.shell import CacheVaultApp
    from cache_vault.ui.theme import apply_app_theme

    install_global_hook()
    apply_app_theme()
    app = CacheVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
