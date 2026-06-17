"""Tk / CustomTkinter availability probe for UI tests."""

from __future__ import annotations


def probe_tk_ui() -> tuple[bool, str]:
    """Return (ok, reason). False when Tk or ttk themes cannot initialize."""
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
        if any(token in msg for token in ("tk.tcl", "ttk", ".tcl", "Tk")):
            return False, f"Tk/ttk theme unavailable: {msg[:200]}"
        return False, f"Tk init failed: {msg[:200]}"
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
        if any(token in msg for token in ("tk.tcl", "vistaTheme", "ttk", ".tcl", "Tk")):
            return False, f"CustomTkinter/Tk theme unavailable: {msg[:200]}"
        return False, f"CustomTkinter init failed: {msg[:200]}"
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
