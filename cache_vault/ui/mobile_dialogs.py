"""Mobile Access dialogs — pairing and mobile receipt viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import models
from ..core.lan_ip import lan_ip_guidance, list_lan_ipv4
from ..core.mobile.models import DEFAULT_MOBILE_PORT
from . import theme
from .pairing_help import (
    PAIRING_ERROR,
    PAIRING_PLACEHOLDER,
    pairing_copy_all_text,
    pairing_success_text,
    normalize_device_name,
)


def _copy_to_clipboard(master: ctk.CTk, text: str) -> None:
    master.clipboard_clear()
    master.clipboard_append(text)


class PairAndroidDialog(ctk.CTkToplevel):
    """Desktop pairing for Cache Vault Mobile."""

    def __init__(
        self,
        master,
        on_pair: Callable[[str, str], tuple[str, str]],
        *,
        port: int = DEFAULT_MOBILE_PORT,
    ):
        super().__init__(master)
        self.title(f"{brand.TERM_MOBILE_ACCESS} — Pair Android Device")
        self.geometry("520x580")
        self.resizable(False, False)
        self._on_pair = on_pair
        self._port = int(port or DEFAULT_MOBILE_PORT)
        self._lan_ips = list_lan_ipv4()
        self._device_id: str | None = None
        self._token: str | None = None

        ctk.CTkLabel(self, text="Pair Android Device",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self,
            text=f"Open {brand.MOBILE_PRODUCT_NAME} on your phone and choose "
                 f"Connect to My PC.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            wraplength=480, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 4))
        ctk.CTkLabel(
            self,
            text="Manual setup is available for this MVP. QR pairing is coming next.",
            anchor="w", justify="left", text_color=brand.STAMP_GOLD,
            wraplength=480, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=16, pady=(0, 8))

        self._lan_label = ctk.CTkLabel(
            self,
            text=lan_ip_guidance(self._lan_ips, port=self._port),
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            wraplength=480, font=ctk.CTkFont(size=10),
        )
        self._lan_label.pack(anchor="w", padx=16, pady=(0, 8))

        ctk.CTkLabel(self, text="Device name (optional):", anchor="w").pack(
            anchor="w", padx=16, pady=(8, 0))
        self._name = ctk.CTkEntry(self, placeholder_text="Android Phone")
        self._name.pack(fill="x", padx=16, pady=4)

        self._gen_btn = ctk.CTkButton(
            self, text="Generate pairing credentials",
            command=self._generate, **theme.primary_button(),
        )
        self._gen_btn.pack(anchor="w", padx=16, pady=10)

        self._out = ctk.CTkTextbox(self, height=200, wrap="word")
        self._out.pack(fill="both", expand=True, padx=16, pady=4)
        self._set_output(PAIRING_PLACEHOLDER)

        copy_row = ctk.CTkFrame(self, fg_color="transparent")
        copy_row.pack(fill="x", padx=16, pady=4)
        self._copy_buttons: list[ctk.CTkButton] = []
        for label, cmd in (
            ("Copy Host/IP", self._copy_host),
            ("Copy Port", self._copy_port),
            ("Copy Device ID", self._copy_device_id),
            ("Copy Token", self._copy_token),
            ("Copy All Setup Info", self._copy_all),
        ):
            btn = ctk.CTkButton(
                copy_row, text=label, width=120, height=28,
                command=cmd, state="disabled", **theme.secondary_button(),
            )
            btn.pack(side="left", padx=(0, 6), pady=2)
            self._copy_buttons.append(btn)

        ctk.CTkLabel(
            self, text="QR code will appear here in a future update.\n"
                       "Store the token securely — it is shown once.",
            anchor="w", text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=16, pady=(0, 4))

        ctk.CTkButton(self, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(anchor="e", padx=16, pady=(0, 12))
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=True)

    def _set_output(self, text: str) -> None:
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.insert("1.0", text)
        self._out.configure(state="disabled")

    def _set_copy_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in self._copy_buttons:
            btn.configure(state=state)

    def _generate(self) -> None:
        self._gen_btn.configure(state="disabled")
        self.update_idletasks()
        try:
            self._lan_ips = list_lan_ipv4()
            self._lan_label.configure(
                text=lan_ip_guidance(self._lan_ips, port=self._port))
            name = normalize_device_name(self._name.get())
            device_id = models.new_id()
            device_id, token = self._on_pair(device_id, name)
            self._device_id = device_id
            self._token = token
            self._set_output(pairing_success_text(
                device_id=device_id, token=token, port=self._port, ips=self._lan_ips))
            self._set_copy_enabled(True)
        except Exception:  # noqa: BLE001 — show inline error, never crash GUI
            self._device_id = None
            self._token = None
            self._set_output(PAIRING_ERROR)
            self._set_copy_enabled(False)
        finally:
            self._gen_btn.configure(state="normal")

    def _copy_host(self) -> None:
        if self._lan_ips:
            _copy_to_clipboard(self, self._lan_ips[0])

    def _copy_port(self) -> None:
        _copy_to_clipboard(self, str(self._port))

    def _copy_device_id(self) -> None:
        if self._device_id:
            _copy_to_clipboard(self, self._device_id)

    def _copy_token(self) -> None:
        if self._token:
            _copy_to_clipboard(self, self._token)

    def _copy_all(self) -> None:
        if self._device_id and self._token:
            _copy_to_clipboard(self, pairing_copy_all_text(
                device_id=self._device_id,
                token=self._token,
                port=self._port,
                ips=self._lan_ips,
            ))


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
