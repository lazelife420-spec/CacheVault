"""BUG-6 regression: win_mouse must use pointer-safe WndProc subclassing.

No real window is subclassed here. We assert the module resolves the *Ptr*
APIs and a pointer-sized return type, which is what keeps 64-bit Python from
truncating the WndProc pointer.
"""

import ctypes
import inspect

from cache_vault.core import win_mouse


def test_long_ptr_is_pointer_sized():
    assert win_mouse.LONG_PTR is ctypes.c_ssize_t
    assert ctypes.sizeof(win_mouse.LONG_PTR) == ctypes.sizeof(ctypes.c_void_p)


def test_source_uses_pointer_safe_window_long():
    src = inspect.getsource(win_mouse)
    # The pointer-safe variants must be preferred.
    assert "SetWindowLongPtrW" in src
    assert "GetWindowLongPtrW" in src
    # The legacy truncating helpers must not be called directly anymore.
    assert "win32gui.SetWindowLong(" not in src
    assert "win32gui.GetWindowLong(" not in src
