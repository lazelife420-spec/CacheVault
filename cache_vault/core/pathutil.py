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


def is_local_file(text: str) -> bool:
    """True for an existing local file (not a directory)."""
    if not is_local_path(text):
        return False
    return os.path.isfile(clean_path(text))


def open_path(text: str) -> bool:
    """Open a local folder with the OS default handler.

    Files are not opened here — use the editable-copy flow so originals stay
    immutable. Returns True if the open was attempted.
    """
    if not target_exists(text):
        return False
    path = clean_path(text)
    if not os.path.isdir(path):
        return False
    try:
        os.startfile(path)  # type: ignore[attr-defined]  # Windows-only
        return True
    except Exception:  # noqa: BLE001
        return False


def open_file(text: str) -> bool:
    """Open an existing local file with the OS default handler."""
    if not is_local_file(text):
        return False
    try:
        os.startfile(clean_path(text))  # type: ignore[attr-defined]  # Windows-only
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
