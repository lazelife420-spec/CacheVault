"""Shared dialog hotkey recording helper."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk


class DialogHotkeyRecorder:
    """Hardened in-dialog shortcut recorder for CTk toplevels."""

    def __init__(
        self,
        owner: ctk.CTkToplevel,
        *,
        entry: ctk.CTkEntry,
        button: ctk.CTkButton,
        normalize_keysym: Callable[[str], str | None],
        modifier_keysyms: dict[str, str],
        on_complete: Callable[[], None],
        on_hint: Callable[[str], None] | None = None,
        button_idle_text: str = "Press shortcut now",
        button_recording_text: str = "Recording...",
    ) -> None:
        self._owner = owner
        self._entry = entry
        self._button = button
        self._normalize_keysym = normalize_keysym
        self._modifier_keysyms = modifier_keysyms
        self._on_complete = on_complete
        self._on_hint = on_hint
        self._button_idle_text = button_idle_text
        self._button_recording_text = button_recording_text
        self._recording = False
        self._held: set[str] = set()
        self._bind_ids: dict[str, str] = {}

    @property
    def recording(self) -> bool:
        return self._recording

    def toggle(self) -> None:
        if self._recording:
            self.stop(cancelled=True)
            return
        if not self._alive(self._owner):
            return
        self._recording = True
        self._held.clear()
        self._set_button_text(self._button_recording_text)
        self._set_hint("Press keys now... Esc to cancel.")
        self._bind_ids["<KeyPress>"] = self._owner.bind("<KeyPress>", self._on_key_press, add="+")
        self._bind_ids["<KeyRelease>"] = self._owner.bind("<KeyRelease>", self._on_key_release, add="+")
        self._bind_ids["<Escape>"] = self._owner.bind("<Escape>", self._on_escape, add="+")
        try:
            self._owner.focus_force()
        except Exception:  # noqa: BLE001
            pass

    def stop(self, *, cancelled: bool) -> None:
        if self._recording:
            self._recording = False
            self._held.clear()
            if self._alive(self._owner):
                for seq, bind_id in list(self._bind_ids.items()):
                    try:
                        self._owner.unbind(seq, bind_id)
                    except Exception:  # noqa: BLE001
                        pass
            self._bind_ids.clear()
        self._set_button_text(self._button_idle_text)
        if cancelled:
            self._on_complete()

    def cleanup(self) -> None:
        self.stop(cancelled=False)

    def _on_escape(self, _event):
        self.stop(cancelled=True)
        return "break"

    def _on_key_press(self, event):
        keysym = getattr(event, "keysym", "")
        if keysym in ("Escape", "esc"):
            return self._on_escape(event)
        mod = self._modifier_keysyms.get(keysym)
        if mod:
            self._held.add(mod)
            return "break"
        key = self._normalize_keysym(keysym)
        if key is None:
            self._set_hint("Unsupported key. Use Ctrl/Alt/Shift + letter, digit, F-key, or Esc.")
            return "break"
        order = [m for m in ("ctrl", "alt", "shift", "win") if m in self._held]
        spec = "+".join(order + [key])
        if self._alive(self._entry):
            self._entry.delete(0, "end")
            self._entry.insert(0, spec)
        self.stop(cancelled=False)
        self._on_complete()
        return "break"

    def _on_key_release(self, event):
        mod = self._modifier_keysyms.get(getattr(event, "keysym", ""))
        if mod:
            self._held.discard(mod)
        return "break"

    def _set_button_text(self, text: str) -> None:
        if self._alive(self._button):
            try:
                self._button.configure(text=text)
            except Exception:  # noqa: BLE001
                pass

    def _set_hint(self, text: str) -> None:
        if self._on_hint is None:
            return
        try:
            self._on_hint(text)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def _alive(widget) -> bool:
        try:
            return bool(widget) and bool(widget.winfo_exists())
        except Exception:  # noqa: BLE001
            return False
