"""Write unexpected UI errors to a local crash log (never clip content)."""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def log_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "crash.log"


def write_crash(title: str, exc: BaseException) -> Path:
    """Append a crash record. Returns the log file path."""
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    block = (
        f"\n{'=' * 72}\n"
        f"{stamp}  {title}\n"
        f"{type(exc).__name__}: {exc}\n"
        f"{traceback.format_exc()}\n"
    )
    with path.open("a", encoding="utf-8") as f:
        f.write(block)
    return path


def install_global_hook() -> None:
    """Log uncaught main-thread and worker-thread exceptions to crash.log."""
    prev = sys.excepthook

    def hook(exc_type, exc, tb):
        if exc_type is not None and exc is not None:
            try:
                err = exc if isinstance(exc, BaseException) else Exception(exc)
                write_crash("uncaught exception", err)
            except Exception:  # noqa: BLE001
                pass
        prev(exc_type, exc, tb)

    sys.excepthook = hook

    # Background threads (mobile bridge, mDNS discovery, hotkey listener,
    # foreground-window tracker) crash silently in a windowed packaged build:
    # their exceptions never reach ``sys.excepthook``. Route them to crash.log
    # so intermittent, hard-to-see failures are captured during soak testing.
    import threading

    def thread_hook(args) -> None:
        exc = getattr(args, "exc_value", None)
        if exc is None:
            return
        try:
            name = getattr(getattr(args, "thread", None), "name", "?")
            write_crash(f"uncaught thread exception ({name})", exc)
        except Exception:  # noqa: BLE001
            pass

    threading.excepthook = thread_hook
