"""Cache Vault™ — application entry point.

    python app.py            # launch the desktop app
    python app.py --selftest # headless sanity check (no window, for CI)
"""

from __future__ import annotations

import sys


def _selftest() -> int:
    """Exercise the core pipeline without a display — used by CI smoke checks."""
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault

    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    vault.capture("https://example.com", source_app="test")
    vault.capture("git status", source_app="test")
    secret = vault.capture("sk-abc123DEF456ghi789JKL0", source_app="test")
    assert secret is not None and secret.is_sensitive
    assert len(vault.list_clips()) == 3
    vault.clear_sensitive()
    vault.close()
    print("selftest OK — core capture/classify/sensitive pipeline works")
    return 0


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    try:
        import customtkinter as ctk
    except ImportError:
        sys.stderr.write(
            "customtkinter is not installed.\n"
            "Install dependencies first:  pip install -r requirements.txt\n"
        )
        return 1

    from cache_vault.ui.shell import CacheVaultApp

    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    app = CacheVaultApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
