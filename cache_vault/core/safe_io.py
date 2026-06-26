"""Crash-safe local file writes and corrupt-file recovery.

Doctrine: **fail closed, preserve data, never silently succeed.**

- ``atomic_write_text`` writes to a temp file in the same directory, flushes +
  fsyncs, then ``os.replace``s it into place. A crash mid-write can therefore
  never leave a half-written critical file; readers see either the old content
  or the new content, never a truncated mix.
- ``keep_backup=True`` preserves one last-known-good ``<name>.bak`` before the
  replace, so a single bad save is recoverable.
- ``quarantine_corrupt`` moves an unreadable file aside to
  ``<name>.corrupt-<UTC timestamp>`` instead of letting the next save silently
  overwrite (and destroy) it. The data is preserved for inspection.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def backup_path(path: Path) -> Path:
    return path.with_name(path.name + ".bak")


def atomic_write_text(
    path: str | os.PathLike,
    text: str,
    *,
    encoding: str = "utf-8",
    keep_backup: bool = False,
) -> None:
    """Atomically write *text* to *path* (temp file + fsync + os.replace).

    When *keep_backup* is true, the current file (if any) is copied to
    ``<name>.bak`` before being replaced.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent),
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())

        if keep_backup and path.exists():
            try:
                shutil.copy2(path, backup_path(path))
            except OSError:
                pass  # best-effort; never block the real write on a backup

        os.replace(tmp, path)  # atomic on the same filesystem
        tmp = None
    finally:
        if tmp is not None and tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def quarantine_corrupt(path: str | os.PathLike) -> Optional[Path]:
    """Move an unreadable *path* aside so the next save cannot destroy it.

    Returns the quarantine path, or ``None`` if there was nothing to move /
    the move failed.
    """
    path = Path(path)
    if not path.exists():
        return None
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest = path.with_name(f"{path.name}.corrupt-{stamp}")
    try:
        os.replace(path, dest)
        return dest
    except OSError:
        return None
