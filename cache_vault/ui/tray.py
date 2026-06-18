"""System-tray controller.

Exactly one tray icon. Menu: Open / Pause / Resume / Clear Sensitive / Quit.
Quit must terminate the process cleanly and remove the icon — the shell wires
``on_quit`` to do exactly that.
"""

from __future__ import annotations

import os
from typing import Callable

try:  # pragma: no cover - optional dependency
    import pystray
    from PIL import Image, ImageDraw
    _HAS_TRAY = True
except Exception:  # noqa: BLE001
    _HAS_TRAY = False


def _make_icon_image():
    """The primary (teal) Cache Vault mark for the tray."""
    from .icon import tray_image
    return tray_image(64)


class TrayController:
    def __init__(self, *, on_open: Callable[[], None], on_pause: Callable[[], None],
                 on_resume: Callable[[], None], on_clear_sensitive: Callable[[], None],
                 on_quit: Callable[[], None], on_quick_paste: Callable[[], None] | None = None):
        self._on_open = on_open
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_clear_sensitive = on_clear_sensitive
        self._on_quit = on_quit
        self._on_quick_paste = on_quick_paste
        self._icon = None

    @property
    def available(self) -> bool:
        return _HAS_TRAY

    def start(self) -> None:
        if os.environ.get("CACHE_VAULT_DISABLE_TRAY") == "1":
            return
        if not _HAS_TRAY:
            return
        items = [
            pystray.MenuItem("Open Cache Vault", lambda: self._on_open(), default=True),
        ]
        if self._on_quick_paste is not None:
            items.append(pystray.MenuItem("Quick Paste", lambda: self._on_quick_paste()))
        menu = pystray.Menu(
            *items,
            pystray.MenuItem("Pause Capture", lambda: self._on_pause()),
            pystray.MenuItem("Resume Capture", lambda: self._on_resume()),
            pystray.MenuItem("Clear Sensitive Clips", lambda: self._on_clear_sensitive()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda: self._quit()),
        )
        self._icon = pystray.Icon("CacheVault", _make_icon_image(),
                                  "Cache Vault", menu)
        # run_detached keeps the icon on its own thread; the Tk mainloop owns
        # the main thread.
        self._icon.run_detached()

    def _quit(self) -> None:
        self.stop()
        self._on_quit()

    def stop(self) -> None:
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:  # noqa: BLE001
                pass
            self._icon = None
