"""Vault Macro picker — menu hotkey popup at cursor."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from ..core.vault_macros import Macro, SMART_TYPE_LABELS


class MacroPicker(ctk.CTkToplevel):
    """Popup macro menu — keyboard-first like Quick Paste."""

    def __init__(
        self,
        master,
        macros: list[Macro],
        on_choose: Callable[[Macro], None],
        *,
        title: str = "Vault Macros",
    ):
        super().__init__(master)
        self._macros = macros
        self._on_choose = on_choose
        self._index = 0
        self._rows: list[ctk.CTkFrame] = []
        self._closing = False
        self._settled = False

        self.title(title)
        self.attributes("-topmost", True)
        h = min(486, 96 + 44 * max(len(macros), 1))
        self.geometry(self._cursor_geometry(460, h))
        self.resizable(False, False)
        self.bind("<FocusOut>", self._on_focus_out)

        ctk.CTkLabel(
            self,
            text="Vault Macros   —   ↑/↓ select · 1–9 run · Enter run · Esc cancel",
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=("gray40", "gray65"),
        ).pack(fill="x", padx=12, pady=(10, 4))

        self._list = ctk.CTkScrollableFrame(self, fg_color=("gray96", "gray16"))
        self._list.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        if not macros:
            ctk.CTkLabel(self._list, text="No macros available.",
                         text_color=("gray50", "gray55")).pack(pady=30)
        else:
            for i, macro in enumerate(macros):
                self._rows.append(self._build_row(i, macro))
            self._highlight()

        self.bind("<Up>", lambda _e: self._move(-1))
        self.bind("<Down>", lambda _e: self._move(1))
        self.bind("<Return>", lambda _e: self._choose(self._index))
        self.bind("<KP_Enter>", lambda _e: self._choose(self._index))
        self.bind("<Escape>", lambda _e: self._cancel())
        for n in range(1, 10):
            self.bind(str(n), lambda _e, k=n - 1: self._choose(k))

        self.after(20, self.focus_popup)
        self.after(140, self.focus_popup)
        self.after(350, lambda: setattr(self, "_settled", True))

    def _build_row(self, i: int, macro: Macro) -> ctk.CTkFrame:
        row = ctk.CTkFrame(self._list, corner_radius=6)
        row.pack(fill="x", padx=4, pady=2)
        num = f"{i + 1}" if i < 9 else " "
        label = SMART_TYPE_LABELS.get(macro.smart_type, macro.smart_type)
        trig = macro.trigger_value or macro.trigger_type
        ctk.CTkLabel(row, text=num, width=18,
                     font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(8, 2))
        ctk.CTkLabel(row, text=f"{macro.name} · {label} · {trig}",
                     anchor="w", wraplength=340).pack(side="left", fill="x", expand=True, padx=4, pady=6)
        for w in (row, *row.winfo_children()):
            w.bind("<Button-1>", lambda _e, k=i: self._choose(k))
            w.bind("<Enter>", lambda _e, k=i: self._set_index(k))
        return row

    def _set_index(self, i: int) -> None:
        self._index = i
        self._highlight()

    def _move(self, delta: int) -> None:
        if not self._rows:
            return
        self._index = (self._index + delta) % len(self._rows)
        self._highlight()

    def _highlight(self) -> None:
        for i, row in enumerate(self._rows):
            row.configure(fg_color=("gray80", "gray30") if i == self._index else ("gray92", "gray20"))

    def _cancel(self) -> None:
        self._closing = True
        self.destroy()

    def _choose(self, i: int) -> None:
        if self._closing:
            return
        if 0 <= i < len(self._macros):
            macro = self._macros[i]
            self._closing = True
            self.destroy()
            self._on_choose(macro)

    def focus_popup(self) -> None:
        if self._closing or not self.winfo_exists():
            return
        try:
            self.deiconify()
            self.attributes("-topmost", True)
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:  # noqa: BLE001
            pass

    def _on_focus_out(self, _event=None) -> None:
        if self._closing or not self._settled:
            return
        try:
            if self.focus_get() is None:
                self._cancel()
        except Exception:  # noqa: BLE001
            pass

    def destroy(self) -> None:
        self._closing = True
        try:
            self.grab_release()
        except Exception:  # noqa: BLE001
            pass
        super().destroy()

    def _cursor_geometry(self, w: int, h: int) -> str:
        px, py = self.winfo_pointerx(), self.winfo_pointery()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        x = min(px + 4, sw - w - 8)
        y = min(py + 4, sh - h - 8)
        return f"{w}x{h}+{max(8, x)}+{max(8, y)}"
