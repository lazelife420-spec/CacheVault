"""Mobile Access dialogs — pairing placeholder and receipt viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import models
from ..core.mobile.models import DEFAULT_MOBILE_PORT
from . import theme


class PairAndroidDialog(ctk.CTkToplevel):
    """Desktop pairing for Cache Vault Mobile."""

    def __init__(self, master, on_pair: Callable[[str, str], tuple[str, str]]):
        super().__init__(master)
        self.title(f"{brand.TERM_MOBILE_ACCESS} — Pair Android Device")
        self.geometry("480x440")
        self.resizable(False, False)
        self._on_pair = on_pair

        ctk.CTkLabel(self, text="Pair Android Device",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self,
            text=f"Open {brand.MOBILE_PRODUCT_NAME} on your phone and choose "
                 f"Connect to My PC.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            wraplength=440, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text="Manual setup is available for this MVP. QR pairing is coming next.",
            anchor="w", justify="left", text_color=brand.STAMP_GOLD,
            wraplength=440, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Device name:", anchor="w").pack(
            anchor="w", padx=16, pady=(8, 0))
        self._name = ctk.CTkEntry(self, placeholder_text="e.g. Pixel 8")
        self._name.pack(fill="x", padx=16, pady=4)

        ctk.CTkButton(self, text="Generate pairing credentials",
                      command=self._generate, **theme.primary_button()
                      ).pack(anchor="w", padx=16, pady=10)

        self._out = ctk.CTkTextbox(self, height=160, wrap="word")
        self._out.pack(fill="both", expand=True, padx=16, pady=4)
        self._out.configure(state="disabled")

        ctk.CTkLabel(
            self, text="QR code will appear here in a future update.\n"
                       "Store the token securely — it is shown once.",
            anchor="w", text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkButton(self, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(anchor="e", padx=16, pady=(0, 12))
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=True)

    def _generate(self) -> None:
        name = self._name.get().strip() or "Android device"
        device_id = models.new_id()
        device_id, token = self._on_pair(device_id, name)
        payload = (
            f"Device ID: {device_id}\n"
            f"Token (show once): {token}\n\n"
            f"Future QR payload will include host, port ({DEFAULT_MOBILE_PORT} default), "
            f"device id, and token.\n\n"
            f"{brand.MOBILE_PROMISE}"
        )
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.insert("1.0", payload)
        self._out.configure(state="disabled")


class MobileAccessReceiptsDialog(ctk.CTkToplevel):
    def __init__(self, master, receipts: list[dict]):
        super().__init__(master)
        self.title(f"{brand.TERM_MOBILE_ACCESS_RECEIPTS}")
        self.geometry("640x460")
        ctk.CTkLabel(
            self, text=f"{brand.TERM_MOBILE_ACCESS_RECEIPTS}",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self, text=brand.MOBILE_PROMISE, anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 8))
        box = ctk.CTkTextbox(self, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=8)
        if not receipts:
            box.insert("1.0", "No mobile access receipts yet.")
        for r in receipts:
            ts = (r.get("timestamp") or "")[:19].replace("T", " ")
            line = (
                f"{ts}  {r.get('result','?'):<8}  {r.get('action','?'):<22}  "
                f"{r.get('route','')}  {r.get('device_name') or r.get('device_id') or ''}"
                f"  {r.get('reason') or ''}\n"
            )
            box.insert("end", line)
        box.configure(state="disabled")
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=False)


class PairedDevicesDialog(ctk.CTkToplevel):
    def __init__(self, master, devices: list[dict],
                 on_revoke: Callable[[str], None]):
        super().__init__(master)
        self.title("Paired Devices")
        self.geometry("440x320")
        self._on_revoke = on_revoke

        ctk.CTkLabel(self, text="Paired Devices",
                     font=ctk.CTkFont(size=15, weight="bold")
                     ).pack(anchor="w", padx=16, pady=(14, 6))
        frame = ctk.CTkScrollableFrame(self, height=200)
        frame.pack(fill="both", expand=True, padx=12, pady=4)
        if not devices:
            ctk.CTkLabel(frame, text="No paired devices yet.",
                         text_color=brand.MUTED_FG).pack(pady=20)
        for d in devices:
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            label = f"{d.get('device_name', '?')}  ({d.get('device_id', '')[:8]}…)"
            ctk.CTkLabel(row, text=label, anchor="w").pack(side="left", padx=4)
            ctk.CTkButton(
                row, text="Revoke", width=70, command=lambda i=d["device_id"]: self._revoke(i),
                **theme.destructive_button(),
            ).pack(side="right", padx=4)
        ctk.CTkButton(self, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(anchor="e", padx=16, pady=12)
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=True)

    def _revoke(self, device_id: str) -> None:
        self._on_revoke(device_id)
        self.destroy()
