"""Work-area-aware window geometry helpers.

Tk on Windows has no work-area API, so this module reads the primary
display's work area (screen minus taskbar) via SystemParametersInfoW and
falls back to the full screen rect when unavailable (non-Windows platforms,
test doubles, unusual sessions).

The clamp/parse helpers are pure functions so they can be exercised
headlessly with synthetic rects; only ``query_work_area`` touches the OS.

Why this exists: the main window used to open at a hardcoded ``1200x760``
regardless of the display, and the Settings Hub / Pair Android dialog used
fixed sizes that could exceed short (e.g. 768px) screens. The main window
now also persists its geometry (size + position + maximized state) across
launches via ``Settings.window_geometry`` / ``Settings.window_maximized``.
"""

from __future__ import annotations

import ctypes
import re
import sys

# "WxH+X+Y" with signed offsets. Offsets are recorded from winfo_rootx/rooty,
# which can be negative on monitors left of / above the primary display.
# Raw saved values are NEVER handed to Tk directly: they are always run
# through fit_geometry() first, which clamps them into the *current* work
# area (whose coordinates are non-negative), so Tk only ever sees valid
# "WxH+X+Y" strings.
_GEOMETRY_RE = re.compile(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$")

# SPI_GETWORKAREA — retrieves the size of the primary display's work area.
_SPI_GETWORKAREA = 0x0030


def window_scaling(widget) -> float:
    """CustomTkinter window-scaling factor (logical design units -> physical
    pixels) for ``widget``'s display.

    CTk activates Windows DPI awareness and rewrites ``geometry()`` /
    ``minsize()`` sizes by this factor (offsets pass through untouched),
    while ``winfo_*`` and the OS work-area query speak raw physical pixels.
    All size math that crosses that boundary must convert; 1.0 when
    customtkinter is unavailable or reports a non-positive factor.
    """
    try:
        import customtkinter as ctk

        factor = float(ctk.ScalingTracker.get_window_scaling(widget))
    except Exception:  # noqa: BLE001 - headless tests / non-CTk windows
        return 1.0
    return factor if factor > 0 else 1.0


def to_physical_size(w: int, h: int, scaling: float) -> tuple[int, int]:
    """Logical (CTk design) size -> physical pixels."""
    return (round(int(w) * scaling), round(int(h) * scaling))


def to_logical_size(w: int, h: int, scaling: float) -> tuple[int, int]:
    """Physical pixels -> logical (CTk design) size."""
    return (round(int(w) / scaling), round(int(h) / scaling))


def query_work_area(widget) -> tuple[int, int, int, int]:
    """Return ``(x, y, w, h)`` of the primary display's work area.

    Returns ``(0, 0, 0, 0)`` when the work area cannot be determined
    (no real display metrics, unusual session). Callers treat the zero
    rect as "skip clamping" rather than guessing.
    """
    try:
        sw = int(widget.winfo_screenwidth())
        sh = int(widget.winfo_screenheight())
    except Exception:  # noqa: BLE001 - test doubles / early teardown
        return (0, 0, 0, 0)
    if sw <= 0 or sh <= 0:
        return (0, 0, 0, 0)
    if sys.platform.startswith("win"):
        try:

            class _RECT(ctypes.Structure):
                _fields_ = [
                    ("left", ctypes.c_long),
                    ("top", ctypes.c_long),
                    ("right", ctypes.c_long),
                    ("bottom", ctypes.c_long),
                ]

            rect = _RECT()
            if ctypes.windll.user32.SystemParametersInfoW(
                _SPI_GETWORKAREA, 0, ctypes.byref(rect), 0
            ):
                w, h = rect.right - rect.left, rect.bottom - rect.top
                # Sanity: a work area must be a non-empty subset of the
                # screen. A bogus reply falls back to the full screen rect.
                if 0 < w <= sw and 0 < h <= sh:
                    return (rect.left, rect.top, w, h)
        except Exception:  # noqa: BLE001 - never let OS probing break startup
            pass
    return (0, 0, sw, sh)


def parse_geometry(text: str | None) -> tuple[int, int, int, int] | None:
    """Parse a persisted ``WxH+X+Y`` geometry string into ``(w, h, x, y)``.

    Returns ``None`` for anything malformed, non-positive, or with missing
    offsets — callers must treat that as "no valid saved geometry" and fall
    back to the default startup size, never guess.
    """
    if not text:
        return None
    match = _GEOMETRY_RE.match(str(text).strip())
    if not match:
        return None
    w, h, x, y = (int(g) for g in match.groups())
    if w <= 0 or h <= 0:
        return None
    return (w, h, x, y)


def format_geometry(w: int, h: int, x: int, y: int) -> str:
    """Format ``(w, h, x, y)`` as a signed-offset geometry string."""
    return f"{int(w)}x{int(h)}{int(x):+d}{int(y):+d}"


def clamp_size(
    w: int, h: int, area: tuple[int, int, int, int], min_w: int = 1, min_h: int = 1
) -> tuple[int, int]:
    """Cap ``w``/``h`` to the work area, never below the window's minimums.

    If the work area itself is smaller than the minimums (tiny displays),
    the minimums win — Tk enforces them anyway, and an overflowing window
    with reachable title bar beats a uselessly small one.
    """
    _ax, _ay, aw, ah = area
    w = max(int(min_w), min(int(w), int(aw)))
    h = max(int(min_h), min(int(h), int(ah)))
    return (w, h)


def clamp_position(
    x: int, y: int, w: int, h: int, area: tuple[int, int, int, int]
) -> tuple[int, int]:
    """Keep the window fully inside the work area when it fits.

    When the window is larger than the work area (minimum-size floor), the
    top-left corner is pinned at the work-area origin so the title bar —
    and therefore the window itself — stays reachable.
    """
    ax, ay, aw, ah = area
    if w >= aw:
        x = ax
    else:
        x = min(max(int(x), ax), ax + aw - w)
    if h >= ah:
        y = ay
    else:
        y = min(max(int(y), ay), ay + ah - h)
    return (x, y)


def fit_geometry(
    w: int,
    h: int,
    x: int,
    y: int,
    area: tuple[int, int, int, int],
    min_w: int = 1,
    min_h: int = 1,
) -> tuple[int, int, int, int]:
    """Clamp size then position so the window fits the current work area."""
    w, h = clamp_size(w, h, area, min_w, min_h)
    x, y = clamp_position(x, y, w, h, area)
    return (w, h, x, y)
