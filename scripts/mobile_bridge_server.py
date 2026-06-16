"""Keep the mobile bridge alive for device smoke (uses current source, not dist exe)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cache_vault.core.mobile.bridge import MobileBridge  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402


def main() -> int:
    vault = Vault()
    bridge = MobileBridge(vault)
    bridge.sync(vault.settings)
    if not bridge.is_running:
        print("mobile bridge failed to start", flush=True)
        return 1
    print("mobile bridge listening", flush=True)
    try:
        while bridge.is_running:
            time.sleep(1.0)
    except KeyboardInterrupt:
        pass
    bridge.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
