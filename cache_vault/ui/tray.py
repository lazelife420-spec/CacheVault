"""System-tray controller.

Exactly one tray icon. Menu: Open / Pause / Resume / Clear Sensitive / Quit.
Quit must terminate the process cleanly and remove the icon — the shell wires
``on_quit`` to do exactly that.
"""

from __future__ import annotations

from typing import Callable

try:  # pragma: no cover - optional dependency
    import pystray
    from PIL import Image, ImageDraw
    _HAS_TRAY = True
except Exception:  # noqa: BLE001
    _HAS_TRAY = False


def _make_icon_image():
    """A simple vault-ish glyph drawn at runtime (no asset files needed)."""
    img = Image.new("RGB", (64, 64), (24, 26, 32))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([10, 10, 54, 54], radius=8, outline=(120, 200, 160), width=3)
    d.ellipse([26, 26, 38, 38], outline=(120, 200, 160), width=3)
    d.line([32, 32, 32, 48], fill=(120, 200, 160), width=3)
    return img


class TrayController:
    def __init__(self, *, on_open: Callable[[], None], on_pause: Callable[[], None],
                 on_resume: Callable[[], None], on_clear_sensitive: Callable[[], None],
                 on_quit: Callable[[], None]):
        self._on_open = on_open
        self._on_pause = on_pause
        self._on_resume = on_resume
        self._on_clear_sensitive = on_clear_sensitive
        self._on_quit = on_quit
        self._icon = None

    @property
    def available(self) -> bool:
        return _HAS_TRAY

    def start(self) -> None:
        if not _HAS_TRAY:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Open Cache Vault", lambda: self._on_open(), default=True),
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
