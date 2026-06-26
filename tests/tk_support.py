"""Tk / CustomTkinter availability probe for UI tests.

The probe constructs a real ``tk.Tk()`` instance so that runner-image
environments where ``import tkinter`` succeeds but the Tcl/Tk runtime files
(``tk.tcl``, ``init.tcl``, ``vistaTheme.tcl``, …) are missing or broken are
detected here rather than inside individual test bodies.

``probe_tk_ui()`` returns ``(True, "")`` only when the full stack —
tkinter import, ``tk.Tk()`` construction, ``ttk.Label``, and
``customtkinter.CTk()`` — all succeed without raising.
"""

from __future__ import annotations

# Tokens that indicate a missing/broken Tcl/Tk runtime rather than a real
# application error.  Any exception whose str() contains one of these tokens
# is treated as "Tk unavailable" rather than a test failure.
_TCL_UNAVAILABLE_TOKENS = (
    "tk.tcl",
    "init.tcl",
    "ttk",
    ".tcl",
    "Tk",
    "vistaTheme",
    "Can't find",
    "wasn't installed",
)


def _tcl_unavailable(exc: BaseException) -> bool:
    msg = str(exc)
    return any(token in msg for token in _TCL_UNAVAILABLE_TOKENS)


def probe_tk_ui() -> tuple[bool, str]:
    """Return ``(ok, reason)``.

    ``ok`` is ``False`` — and the reason string is non-empty — whenever the
    Tk/CustomTkinter UI stack cannot be initialised in the current environment.
    Tests decorated with ``@pytest.mark.skipif(not ok, reason=reason)`` will
    be skipped cleanly instead of failing with a ``TclError``.
    """
    try:
        import tkinter as tk
        from tkinter import ttk
    except Exception as exc:  # noqa: BLE001
        return False, f"tkinter unavailable: {exc}"

    root = None
    try:
        root = tk.Tk()
        root.withdraw()
        ttk.Label(root, text="probe")
        root.update_idletasks()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if _tcl_unavailable(exc):
            return False, f"Tk/ttk runtime unavailable: {msg[:240]}"
        return False, f"Tk init failed: {msg[:240]}"
    finally:
        if root is not None:
            try:
                root.destroy()
            except Exception:  # noqa: BLE001
                pass

    try:
        import customtkinter as ctk
    except Exception as exc:  # noqa: BLE001
        return False, f"customtkinter unavailable: {exc}"

    ctk_root = None
    ctk_top = None
    try:
        ctk_root = ctk.CTk()
        ctk_root.withdraw()
        ctk_top = ctk.CTkToplevel(ctk_root)
        ctk_top.withdraw()
        ctk_top.update_idletasks()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        msg = str(exc)
        if _tcl_unavailable(exc):
            return False, f"CustomTkinter/Tk runtime unavailable: {msg[:240]}"
        return False, f"CustomTkinter init failed: {msg[:240]}"
    finally:
        if ctk_top is not None:
            try:
                ctk_top.destroy()
            except Exception:  # noqa: BLE001
                pass
        if ctk_root is not None:
            try:
                ctk_root.destroy()
            except Exception:  # noqa: BLE001
                pass
