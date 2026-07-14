"""System-tray controller.

Exactly one tray icon. Native Win32 tray menus cannot be themed with the app's
colors/fonts, so we improve clarity instead: a title header, grouped sections,
and a single checkable "Pause Capture" toggle that mirrors live capture state.
Quit must terminate the process cleanly and remove the icon — the shell wires
``on_quit`` to do exactly that.
"""

from __future__ import annotations

import os
from typing import Callable

from .. import brand

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
    def __init__(self, *, on_open: Callable[[], None],
                 on_toggle_pause: Callable[[], None],
                 on_clear_sensitive: Callable[[], None],
                 on_quit: Callable[[], None],
                 is_paused: Callable[[], bool] | None = None,
                 on_quick_paste: Callable[[], None] | None = None,
                 on_macro_menu: Callable[[], None] | None = None):
        self._on_open = on_open
        self._on_toggle_pause = on_toggle_pause
        self._on_clear_sensitive = on_clear_sensitive
        self._on_quit = on_quit
        self._is_paused = is_paused or (lambda: False)
        self._on_quick_paste = on_quick_paste
        self._on_macro_menu = on_macro_menu
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
            pystray.MenuItem(brand.PRODUCT_NAME, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Cache Vault", lambda: self._on_open(), default=True),
        ]
        if self._on_quick_paste is not None:
            items.append(pystray.MenuItem("Quick Paste", lambda: self._on_quick_paste()))
        if self._on_macro_menu is not None:
            items.append(pystray.MenuItem("Macro Menu", lambda: self._on_macro_menu()))
        menu = pystray.Menu(
            *items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                "Pause Capture",
                lambda: self._on_toggle_pause(),
                checked=lambda _item: self._is_paused(),
            ),
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
