"""Safe local-path handling for clip file actions.

These helpers are intentionally conservative: a clip only counts as a path
clip when it is *clearly* a local Windows file/folder path (drive-letter or
UNC). URLs are never treated as paths, and clip text is never executed as a
shell command. Explorer is invoked with argument lists (never a shell string),
so clip content cannot inject commands.
"""

from __future__ import annotations

import os
import subprocess

from .classify import UNC_PATH_RE, WINDOWS_PATH_RE


def clean_path(text: str) -> str:
    """Strip surrounding quotes/whitespace from a copied path."""
    return (text or "").strip().strip('"').strip("'").strip()


def is_local_path(text: str) -> bool:
    """True only for a clearly local Windows drive-letter or UNC path."""
    candidate = clean_path(text)
    if not candidate or "\n" in candidate:
        return False
    # Reject anything with a URL scheme outright (e.g. http://, file://).
    if "://" in candidate:
        return False
    return bool(WINDOWS_PATH_RE.match(candidate) or UNC_PATH_RE.match(candidate))


def target_exists(text: str) -> bool:
    if not is_local_path(text):
        return False
    return os.path.exists(clean_path(text))


def parent_dir(text: str) -> str:
    return os.path.dirname(clean_path(text).rstrip("\\/"))


def parent_exists(text: str) -> bool:
    if not is_local_path(text):
        return False
    parent = parent_dir(text)
    return bool(parent) and os.path.isdir(parent)


def open_path(text: str) -> bool:
    """Open a local file/folder with the OS default handler. No URLs, no shell.

    Returns True if the open was attempted. Refuses anything that is not a
    clearly local, existing path.
    """
    if not target_exists(text):
        return False
    path = clean_path(text)
    try:
        os.startfile(path)  # type: ignore[attr-defined]  # Windows-only
        return True
    except Exception:  # noqa: BLE001
        return False


def reveal_in_explorer(text: str) -> bool:
    """Reveal a path in Explorer. Selects the item if it exists; otherwise
    opens the parent folder when that still exists. Never runs a shell."""
    if not is_local_path(text):
        return False
    path = clean_path(text)
    try:
        if os.path.exists(path):
            # /select highlights the item; path passed as a separate arg.
            subprocess.run(["explorer", "/select,", path], check=False)
            return True
        parent = parent_dir(text)
        if parent and os.path.isdir(parent):
            os.startfile(parent)  # type: ignore[attr-defined]
            return True
    except Exception:  # noqa: BLE001
        return False
    return False
