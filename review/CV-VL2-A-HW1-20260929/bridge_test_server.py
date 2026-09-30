"""Minimal bridge test server for emulator 423 gate verification.

Starts a real MobileBridge HTTP server on 127.0.0.1:8742 with the vault
locked. The Android emulator reaches the host's loopback via 10.0.2.2.

Usage: py bridge_test_server.py [locked|unlocked]
  locked   → bridge returns 423 for all non-pairing routes (default)
  unlocked → bridge returns 401 (no paired device) for protected routes
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "locked"
    tmpdir = tempfile.mkdtemp(prefix="cv_bridge_test_")
    os.environ["LOCALAPPDATA"] = tmpdir

    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core import vault_lock
    from cache_vault.core.mobile.bridge import MobileBridge

    settings = Settings.load()
    settings.mobile_access_enabled = True
    settings.mobile_access_port = 8742
    settings.mobile_access_bind_host = "127.0.0.1"
    settings.capture_paused = True
    settings.save()

    storage = VaultStorage(":memory:")
    vault = Vault(storage=storage, settings=settings)

    lock_state = {"state": vault_lock.VaultLockState.LOCKED if mode == "locked"
                  else vault_lock.VaultLockState.UNLOCKED}

    bridge = MobileBridge(vault, lock_state_provider=lambda: lock_state["state"])

    # Monkey-patch handle() to log requests
    _orig_handle = bridge.handle
    def _logged_handle(*args, **kwargs):
        method = args[0] if args else kwargs.get("method", "?")
        path = args[1] if len(args) > 1 else kwargs.get("path", "?")
        code, body = _orig_handle(*args, **kwargs)
        print(f"[{time.strftime('%H:%M:%S')}] {method} {path} -> {code}", flush=True)
        return code, body
    bridge.handle = _logged_handle

    bridge.sync(settings)

    if not bridge.is_running:
        print(f"ERROR: bridge failed to start on 127.0.0.1:8742")
        return 1

    print(f"Bridge test server running on 127.0.0.1:8742 (mode={mode})")
    print(f"Emulator can reach via 10.0.2.2:8742")
    print(f"Vault lock state: {lock_state['state'].value}")
    print(f"Press Ctrl+C to stop.", flush=True)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        bridge.stop()
        print("Bridge stopped.")

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
