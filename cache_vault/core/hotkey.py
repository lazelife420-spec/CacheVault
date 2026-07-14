"""Global (system-wide) hotkey support + paste helper.

Uses the Win32 ``RegisterHotKey`` API on a dedicated thread with its own
message loop, so the hotkey works regardless of which application is focused.
Requires ``pywin32``; without it the listener is a no-op and the feature is
simply unavailable (the rest of the app is unaffected).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

try:  # pragma: no cover - optional dependency / Windows only
    import win32con  # type: ignore
    import win32gui  # type: ignore
    _HAS_WIN32 = True
except Exception:  # noqa: BLE001
    _HAS_WIN32 = False


# Win32 modifier flags.
_MODS = {
    "ctrl": 0x0002, "control": 0x0002,
    "alt": 0x0001,
    "shift": 0x0004,
    "win": 0x0008, "super": 0x0008, "meta": 0x0008,
}
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312

# Win32 VK_NUMPAD0..9 — distinct from top-row 0x30..0x39.
_NUMPAD_VK = {f"num{n}": 0x60 + n for n in range(10)}

_NAMED_VK = {
    "space": 0x20, "enter": 0x0D, "return": 0x0D, "tab": 0x09,
    "esc": 0x1B, "escape": 0x1B, "insert": 0x2D, "ins": 0x2D,
    "delete": 0x2E, "del": 0x2E, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    **{f"f{n}": 0x70 + (n - 1) for n in range(1, 13)},
}

_MODIFIER_KEYSYMS = {
    "Shift_L": "shift", "Shift_R": "shift",
    "Control_L": "ctrl", "Control_R": "ctrl",
    "Alt_L": "alt", "Alt_R": "alt",
    "Super_L": "win", "Super_R": "win", "Win_L": "win", "Win_R": "win",
}

_KEYSYM_ALIASES = {
    "Return": "enter", "KP_Enter": "enter", "Escape": "esc", "Tab": "tab",
    "space": "space", "Delete": "delete", "Insert": "insert", "Home": "home",
    "End": "end", "Prior": "pageup", "Next": "pagedown",
}

# Tk KP_* names that map to numpad digits on layouts without dedicated KP_N keys.
_KP_DIGIT_ALIASES = {
    "Insert": "0", "End": "1", "Down": "2", "Next": "3", "Left": "4",
    "Begin": "5", "Right": "6", "Home": "7", "Up": "8", "Prior": "9",
}


def _canonical_mod(part: str) -> str:
    return {"control": "ctrl", "super": "win", "meta": "win"}.get(part, part)


def _canonical_key_token(part: str) -> str:
    """Normalize a single key token for storage / comparison."""
    part = _canonical_mod(part.lower())
    if part.startswith("numpad") and part[6:].isdigit():
        return f"num{part[6:]}"
    if part.startswith("num") and len(part) == 4 and part[3].isdigit():
        return part
    return part


def _parse_parts(spec: str) -> list[str]:
    parts: list[str] = []
    for raw in (spec or "").lower().replace(" ", "").split("+"):
        if not raw:
            continue
        parts.append(_canonical_key_token(raw))
    return parts


def canonical_hotkey_spec(spec: str) -> str:
    """Canonical storage/comparison form, e.g. ``ctrl+num2``."""
    return "+".join(_parse_parts(spec))


def _format_key_display(key: str) -> str:
    key = key.lower()
    if key.startswith("num") and len(key) == 4 and key[3].isdigit():
        return f"Num {key[3]}"
    if len(key) == 1:
        return key.upper()
    if key.lower().startswith("f") and key[1:].isdigit():
        return key.lower()
    return key.capitalize()


def normalize_keysym(keysym: str, keycode: int | None = None) -> str | None:
    """Map a Tk keysym (+ optional keycode) to a hotkey key token."""
    if not keysym:
        return None
    if keysym in _KEYSYM_ALIASES:
        return _KEYSYM_ALIASES[keysym]
    if keysym.startswith("KP_"):
        tail = keysym[3:]
        if tail.isdigit():
            return f"num{tail}"
        digit = _KP_DIGIT_ALIASES.get(tail)
        if digit is not None:
            return f"num{digit}"
    if len(keysym) == 1 and keysym.isalnum():
        if keycode is not None and 0x60 <= keycode <= 0x69:
            return f"num{keycode - 0x60}"
        return keysym.lower()
    if keysym.lower().startswith("f") and keysym[1:].isdigit():
        return keysym.lower()
    return None


def _vk_for(key: str) -> Optional[int]:
    key = key.lower()
    if key in _NUMPAD_VK:
        return _NUMPAD_VK[key]
    if key.startswith("numpad") and key[6:].isdigit():
        n = int(key[6:])
        if 0 <= n <= 9:
            return 0x60 + n
    if len(key) == 1:
        return ord(key.upper())
    return _NAMED_VK.get(key)


def parse_hotkey(spec: str) -> tuple[int, Optional[int]]:
    """Turn ``"ctrl+shift+v"`` into ``(modifier_flags, virtual_key_code)``.

    Returns ``vk = None`` when the spec has no usable main key.
    """
    mods = 0
    vk: Optional[int] = None
    for part in spec.lower().replace(" ", "").split("+"):
        if not part:
            continue
        if part in _MODS:
            mods |= _MODS[part]
        else:
            vk = _vk_for(part)
    return mods, vk


def normalize_hotkey(spec: str) -> str:
    """Human-readable, canonical form for display, e.g. ``Ctrl+Shift+V``."""
    order = ["ctrl", "alt", "shift", "win"]
    parts = _parse_parts(spec)
    mod_parts = [m.capitalize() for m in order if m in parts]
    key_tokens = [p for p in parts if p not in _MODS]
    key_part = _format_key_display(key_tokens[0]) if key_tokens else ""
    return "+".join(mod_parts + ([key_part] if key_part else []))


# Default bindings mirrored from Settings — used for reset/help copy only.
DEFAULT_HOTKEY_BINDINGS: dict[str, str] = {
    "manual_save": "ctrl+shift+c",
    "arm_next": "ctrl+alt+c",
    "ignore_next": "ctrl+shift+x",
    "quick_paste": "ctrl+shift+v",
    "macro_menu": "ctrl+shift+m",
}

# OS / app shortcuts users should avoid reassigning to macros (display hint only).
_WINDOWS_RESERVED_DISPLAY = frozenset({
    "win+v", "alt+tab", "ctrl+c", "ctrl+v", "ctrl+x",
})


def _canonical_key(spec: str) -> str:
    return canonical_hotkey_spec(spec)


def diagnose_hotkey_spec(
    spec: str,
    role: str,
    all_specs: dict[str, str],
    *,
    win32_available: bool | None = None,
    external_specs: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Return ``(kind, message)`` for settings UI status labels.

    *kind* is one of: ``ok``, ``invalid``, ``duplicate``, ``conflict``,
    ``unavailable``, ``reserved``.

    ``external_specs`` maps a raw hotkey string (e.g. a Vault Macro or Hotkey
    Action combo) to a human label describing its owner. A match reports a
    ``conflict`` so the user knows the shortcut is already claimed elsewhere.
    """
    if win32_available is None:
        win32_available = _HAS_WIN32
    raw = (spec or "").strip()
    if not raw:
        return "invalid", "Enter a shortcut like Ctrl+Shift+V"
    _mods, vk = parse_hotkey(raw)
    if vk is None:
        return "invalid", "Missing key — use Ctrl/Alt/Shift + letter or F-key"
    canon_key = _canonical_key(raw)
    dup_roles = [
        r for r, other in all_specs.items()
        if r != role and other.strip() and _canonical_key(other) == canon_key
    ]
    if dup_roles:
        return "duplicate", "Same shortcut used elsewhere in Cache Vault"
    if external_specs:
        for other_spec, label in external_specs.items():
            if other_spec and _canonical_key(other_spec) == canon_key:
                return "conflict", f"Already used by {label}"
    if not win32_available:
        return "unavailable", "Global shortcuts need Windows (pywin32)"
    if canon_key in _WINDOWS_RESERVED_DISPLAY:
        return "reserved", "May conflict with Windows or common app shortcuts"
    return "ok", f"Ready · {normalize_hotkey(raw)}"


class HotkeyListener:
    """Registers a single global hotkey and calls ``on_activate`` when pressed.

    The callback runs on the listener thread; UI code should marshal back to
    the main thread (the shell uses ``after``).
    """

    def __init__(self, spec: str, on_activate: Callable[[], None]):
        self._spec = spec
        self._on_activate = on_activate
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._registered = False

    @property
    def available(self) -> bool:
        return _HAS_WIN32

    @property
    def registered(self) -> bool:
        return self._registered

    def start(self) -> None:
        if not _HAS_WIN32 or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="hotkey-listener",
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not _HAS_WIN32 or not self._hwnd:
            return
        thread = self._thread
        if self._registered:
            try:
                win32gui.UnregisterHotKey(self._hwnd, 1)
            except Exception:  # noqa: BLE001
                pass
        try:
            win32gui.PostMessage(self._hwnd, win32con.WM_DESTROY, 0, 0)
        except Exception:  # noqa: BLE001
            pass
        if thread is not None:
            thread.join(timeout=2.0)

    def _run(self) -> None:  # pragma: no cover - needs Windows desktop
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == _WM_HOTKEY:
                try:
                    self._on_activate()
                except Exception:  # noqa: BLE001
                    pass
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpszClassName = "CacheVaultHotkey"
        wc.lpfnWndProc = wndproc
        try:
            atom = win32gui.RegisterClass(wc)
        except Exception:
            atom = wc.lpszClassName
        self._hwnd = win32gui.CreateWindow(
            atom, "CacheVaultHotkey", 0, 0, 0, 0, 0, 0, 0, 0, None)

        mods, vk = parse_hotkey(self._spec)
        if vk is not None:
            try:
                win32gui.RegisterHotKey(self._hwnd, 1, mods | _MOD_NOREPEAT, vk)
                self._registered = True
            except Exception:  # noqa: BLE001 - hotkey may be taken by another app
                self._registered = False
        win32gui.PumpMessages()
        self._hwnd = None
        self._registered = False
        self._thread = None


class MultiHotkeyListener:
    """Registers multiple global hotkeys on one message loop."""

    _next_class_id = 0

    def __init__(self):
        MultiHotkeyListener._next_class_id += 1
        self._wnd_class = f"CacheVaultMultiHotkey{MultiHotkeyListener._next_class_id}"
        self._bindings: dict[int, tuple[str, Callable[[], None]]] = {}
        self._thread: Optional[threading.Thread] = None
        self._hwnd = None
        self._registered: set[int] = set()

    @property
    def available(self) -> bool:
        return _HAS_WIN32

    def registered_ids(self) -> set[int]:
        """Hotkey ids the OS actually accepted (best-effort snapshot)."""
        return set(self._registered)

    def clear_bindings(self) -> None:
        self._bindings.clear()

    def set_binding(self, hotkey_id: int, spec: str, on_activate: Callable[[], None]) -> None:
        self._bindings[hotkey_id] = (spec, on_activate)

    def start(self) -> None:
        if not _HAS_WIN32 or self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._run, name="multi-hotkey-listener", daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        if not _HAS_WIN32 or not self._hwnd:
            return
        thread = self._thread
        for hid in list(self._registered):
            try:
                win32gui.UnregisterHotKey(self._hwnd, hid)
            except Exception:  # noqa: BLE001
                pass
        try:
            win32gui.PostMessage(self._hwnd, win32con.WM_DESTROY, 0, 0)
        except Exception:  # noqa: BLE001
            pass
        if thread is not None:
            thread.join(timeout=2.0)

    def _run(self) -> None:  # pragma: no cover - needs Windows desktop
        def wndproc(hwnd, msg, wparam, lparam):
            if msg == _WM_HOTKEY:
                hid = int(wparam)
                binding = self._bindings.get(hid)
                if binding:
                    try:
                        binding[1]()
                    except Exception:  # noqa: BLE001
                        pass
                return 0
            if msg == win32con.WM_DESTROY:
                win32gui.PostQuitMessage(0)
                return 0
            return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)

        wc = win32gui.WNDCLASS()
        wc.lpszClassName = self._wnd_class
        wc.lpfnWndProc = wndproc
        try:
            atom = win32gui.RegisterClass(wc)
        except Exception:
            atom = wc.lpszClassName
        self._hwnd = win32gui.CreateWindow(
            atom, self._wnd_class, 0, 0, 0, 0, 0, 0, 0, 0, None)

        self._registered.clear()
        for hid, (spec, _cb) in self._bindings.items():
            mods, vk = parse_hotkey(spec)
            if vk is None:
                continue
            try:
                win32gui.RegisterHotKey(self._hwnd, hid, mods | _MOD_NOREPEAT, vk)
                self._registered.add(hid)
            except Exception:  # noqa: BLE001
                pass
        win32gui.PumpMessages()
        self._hwnd = None
        self._registered.clear()
        self._thread = None


def focus_and_paste(hwnd) -> bool:
    """Restore focus to ``hwnd`` (the app the user was in) and send Ctrl+V."""
    from .paste_delivery import deliver_ctrl_v

    return deliver_ctrl_v(hwnd).ok


def foreground_window():
    from .paste_delivery import foreground_window as _fg

    return _fg()
