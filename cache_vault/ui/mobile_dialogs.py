"""Mobile Access dialogs — pairing and mobile receipt viewer."""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from .. import brand
from ..core import clipboard_out, models
from ..core.lan_ip import advanced_lan_ipv4, list_lan_ipv4, recommended_lan_ipv4
from ..core.mobile.connection_doctor import connection_doctor_text
from ..core.mobile.models import (
    DEFAULT_MOBILE_PORT,
    DEVICE_STATUS_OFFLINE,
    DEVICE_STATUS_ONLINE,
    DEVICE_STATUS_REVOKED,
    DEVICE_STATUS_WAITING_APPROVAL,
    PairedDevice,
    paired_device_status,
)
from . import theme
from .textbox import CacheVaultTextbox
from .pairing_help import (
    PAIRING_ERROR,
    PAIRING_PLACEHOLDER,
    pairing_copy_all_text,
    pairing_success_text,
    normalize_device_name,
)


def _copy_to_clipboard(master: ctk.CTk, text: str) -> None:
    clipboard_out.write_via_tk(master, text)


class PairAndroidDialog(ctk.CTkToplevel):
    """Desktop pairing for Cache Vault Mobile — secure vault connection flow."""

    def __init__(
        self,
        master,
        on_pair: Callable[[str, str], tuple[str, str]],
        *,
        port: int = DEFAULT_MOBILE_PORT,
        bridge_running: bool = False,
        get_doctor_report: Callable[[], dict] | None = None,
        on_revoke_all_and_pair: Callable[[str, str], tuple[str, str]] | None = None,
        has_active_devices: bool = False,
        create_pairing_offer: Callable[[], Any] | None = None,
    ):
        super().__init__(master)
        self.title(f"{brand.TERM_MOBILE_ACCESS} — Pair Android Device")
        self.geometry("540x840")
        self.resizable(False, False)
        self._on_pair = on_pair
        self._on_revoke_all_and_pair = on_revoke_all_and_pair
        self._get_doctor_report = get_doctor_report
        self._create_pairing_offer = create_pairing_offer
        self._port = int(port or DEFAULT_MOBILE_PORT)
        self._lan_ips = list_lan_ipv4()
        self._device_id: str | None = None
        self._token: str | None = None
        self._token_visible = False
        self._advanced_visible = False
        self._active_offer = None

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=8, pady=8)

        ctk.CTkLabel(scroll, text="Pair Android Device",
                     font=ctk.CTkFont(size=16, weight="bold")).pack(
            anchor="w", padx=8, pady=(6, 4))
        ctk.CTkLabel(
            scroll,
            text="Scan QR code from Cache Vault Mobile to connect instantly.",
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            wraplength=500, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=8, pady=(0, 8))

        # QR Code Section
        qr_frame = ctk.CTkFrame(scroll, fg_color=brand.SURFACE_BG)
        qr_frame.pack(fill="x", padx=8, pady=(0, 10))

        ctk.CTkLabel(
            qr_frame, text="Scan with Phone (Recommended)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", padx=12, pady=(10, 4))

        self._qr_image_label = ctk.CTkLabel(qr_frame, text="")
        self._qr_image_label.pack(anchor="center", padx=12, pady=6)

        self._qr_sub_label = ctk.CTkLabel(
            qr_frame,
            text="Open Cache Vault Mobile -> Scan pairing QR\nOffer expires in 5:00",
            anchor="center", justify="center", text_color=brand.MUTED_FG,
            font=ctk.CTkFont(size=11),
        )
        self._qr_sub_label.pack(anchor="center", padx=12, pady=(0, 8))

        qr_btn_row = ctk.CTkFrame(qr_frame, fg_color="transparent")
        qr_btn_row.pack(anchor="center", padx=12, pady=(0, 10))

        ctk.CTkButton(
            qr_btn_row, text="Refresh QR Code", width=120, height=28,
            command=self._generate_qr_offer, **theme.primary_button(),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            qr_btn_row, text="Copy QR Payload", width=120, height=28,
            command=self._copy_qr_payload, **theme.secondary_button(),
        ).pack(side="left", padx=4)

        self._generate_qr_offer()

        # Connection Doctor
        doctor_frame = ctk.CTkFrame(scroll, fg_color=brand.SURFACE_BG)
        doctor_frame.pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkLabel(
            doctor_frame, text="Connection Doctor",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", padx=12, pady=(10, 4))
        self._doctor_label = ctk.CTkLabel(
            doctor_frame,
            text=self._doctor_text(bridge_running),
            anchor="w", justify="left", text_color=brand.MUTED_FG,
            wraplength=480, font=ctk.CTkFont(size=10),
        )
        self._doctor_label.pack(anchor="w", padx=12, pady=(0, 10))

        # Recommended connection
        ctk.CTkLabel(scroll, text="Recommended connection",
                     font=ctk.CTkFont(size=12, weight="bold")).pack(
            anchor="w", padx=8, pady=(4, 2))
        rec_ip = recommended_lan_ipv4(self._lan_ips)
        self._rec_host_label = ctk.CTkLabel(
            scroll,
            text=self._recommended_block(rec_ip),
            anchor="w", justify="left",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=brand.PROOF_TEAL,
        )
        self._rec_host_label.pack(anchor="w", padx=8, pady=(0, 8))

        for step in (
            f"Step 1 — Open {brand.MOBILE_PRODUCT_NAME} on your phone.",
            "Step 2 — Tap Connect to My PC when your PC is found.",
            "Step 3 — Use the pairing code below (or Manual Setup).",
        ):
            ctk.CTkLabel(
                scroll, text=step, anchor="w", justify="left",
                text_color=brand.MUTED_FG, wraplength=500,
                font=ctk.CTkFont(size=10),
            ).pack(anchor="w", padx=8, pady=1)

        ctk.CTkLabel(scroll, text="Device name (optional):", anchor="w").pack(
            anchor="w", padx=8, pady=(10, 0))
        self._name = ctk.CTkEntry(scroll, placeholder_text="Android Phone")
        self._name.pack(fill="x", padx=8, pady=4)

        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=8)
        self._gen_btn = ctk.CTkButton(
            btn_row, text="Generate Fresh Pairing Code",
            command=self._generate, **theme.primary_button(),
        )
        self._gen_btn.pack(side="left", padx=(0, 8))
        if has_active_devices and on_revoke_all_and_pair:
            ctk.CTkButton(
                btn_row, text="Revoke Old Phone + Fresh Pair",
                command=self._revoke_all_generate,
                **theme.destructive_button(),
            ).pack(side="left")

        token_row = ctk.CTkFrame(scroll, fg_color="transparent")
        token_row.pack(fill="x", padx=8, pady=(0, 4))
        self._toggle_token_btn = ctk.CTkButton(
            token_row, text="Show Token", width=100, height=28,
            command=self._toggle_token, state="disabled",
            **theme.secondary_button(),
        )
        self._toggle_token_btn.pack(side="right")

        self._out = CacheVaultTextbox(scroll, height=180, wrap="word")
        self._out.pack(fill="x", padx=8, pady=4)
        self._set_output(PAIRING_PLACEHOLDER)

        copy_row = ctk.CTkFrame(scroll, fg_color="transparent")
        copy_row.pack(fill="x", padx=8, pady=4)
        self._copy_buttons: list[ctk.CTkButton] = []
        for label, cmd in (
            ("Copy All Setup Info", self._copy_all),
            ("Copy Host", self._copy_host),
            ("Copy Port", self._copy_port),
            ("Copy Device ID", self._copy_device_id),
            ("Copy Token", self._copy_token),
        ):
            btn = ctk.CTkButton(
                copy_row, text=label, width=118, height=28,
                command=cmd, state="disabled", **theme.secondary_button(),
            )
            btn.pack(side="left", padx=(0, 4), pady=2)
            self._copy_buttons.append(btn)

        self._adv_btn = ctk.CTkButton(
            scroll, text="Advanced ▼", width=100, height=26,
            command=self._toggle_advanced, **theme.secondary_button(),
        )
        self._adv_btn.pack(anchor="w", padx=8, pady=(4, 0))
        self._adv_label = ctk.CTkLabel(
            scroll, text="", anchor="w", justify="left",
            text_color=brand.MUTED_FG, wraplength=500,
            font=ctk.CTkFont(size=10),
        )

        ctk.CTkLabel(
            scroll,
            text=(
                "Token is hidden by default. Do not share screenshots that reveal "
                "it. After testing, use Revoke All Devices or generate a fresh "
                "code. QR pairing is coming next."
            ),
            anchor="w", justify="left", wraplength=500,
            text_color=brand.STAMP_GOLD, font=ctk.CTkFont(size=10),
        ).pack(anchor="w", padx=8, pady=(8, 4))

        ctk.CTkButton(scroll, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(anchor="e", padx=8, pady=(0, 12))
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=True)

    def _generate_qr_offer(self) -> None:
        rec_ip = recommended_lan_ipv4(self._lan_ips) or "127.0.0.1"
        if self._create_pairing_offer:
            offer = self._create_pairing_offer()
        else:
            from ..core.mobile.pairing_offer import PairingOfferManager
            mgr = PairingOfferManager()
            offer = mgr.create_offer(host=rec_ip, port=self._port)

        self._active_offer = offer
        payload_str = offer.to_qr_payload()

        try:
            import qrcode
            qr = qrcode.QRCode(version=1, box_size=5, border=2)
            qr.add_data(payload_str)
            qr.make(fit=True)
            pil_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(180, 180))
            self._qr_image_label.configure(image=ctk_img, text="")
        except Exception:
            self._qr_image_label.configure(image=None, text="[QR Code Display Available]")

    def _copy_qr_payload(self) -> None:
        if self._active_offer:
            _copy_to_clipboard(self, self._active_offer.to_qr_payload())

    def _doctor_text(self, bridge_running: bool) -> str:
        if self._get_doctor_report:
            report = self._get_doctor_report()
            report = dict(report)
            if not bridge_running:
                report["bridge"] = "Not listening"
            return connection_doctor_text(report)
        status = "Listening" if bridge_running else "Not listening"
        rec = recommended_lan_ipv4(self._lan_ips) or "?"
        return (
            f"Mobile Access: On\nBridge: {status}\n"
            f"Port: {self._port}\nRecommended IP: {rec}"
        )

    @staticmethod
    def _recommended_block(rec_ip: str | None) -> str:
        if not rec_ip:
            return "PC LAN IP: (run ipconfig on your PC)"
        return f"PC found on this Wi-Fi:\n{rec_ip}\n\nPort: {DEFAULT_MOBILE_PORT}"

    def _toggle_advanced(self) -> None:
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            adv = advanced_lan_ipv4(self._lan_ips)
            lines = ["Other adapters (not recommended for phone):"]
            if adv:
                lines.extend(f"  • {ip}" for ip in adv)
            else:
                lines.append("  (none detected)")
            lines.append("127.0.0.1 is not usable from your phone.")
            self._adv_label.configure(text="\n".join(lines))
            self._adv_label.pack(anchor="w", padx=8, pady=(4, 8))
            self._adv_btn.configure(text="Advanced ▲")
        else:
            self._adv_label.pack_forget()
            self._adv_btn.configure(text="Advanced ▼")

    def _set_output(self, text: str) -> None:
        self._out.configure(state="normal")
        self._out.delete("1.0", "end")
        self._out.insert("1.0", text)
        self._out.configure(state="disabled")

    def _set_copy_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for btn in self._copy_buttons:
            btn.configure(state=state)
        self._toggle_token_btn.configure(state=state)

    def _refresh_pairing_display(self) -> None:
        if not self._device_id or not self._token:
            return
        self._set_output(pairing_success_text(
            device_id=self._device_id,
            token=self._token,
            port=self._port,
            ips=self._lan_ips,
            show_token=self._token_visible,
        ))

    def _toggle_token(self) -> None:
        self._token_visible = not self._token_visible
        self._toggle_token_btn.configure(
            text="Hide Token" if self._token_visible else "Show Token")
        self._refresh_pairing_display()

    def _generate(self) -> None:
        self._gen_btn.configure(state="disabled")
        self.update_idletasks()
        try:
            self._lan_ips = list_lan_ipv4()
            rec = recommended_lan_ipv4(self._lan_ips)
            self._rec_host_label.configure(text=self._recommended_block(rec))
            if self._get_doctor_report:
                self._doctor_label.configure(
                    text=self._doctor_text(bridge_running=True))
            name = normalize_device_name(self._name.get())
            device_id = models.new_id()
            device_id, token = self._on_pair(device_id, name)
            self._device_id = device_id
            self._token = token
            self._token_visible = False
            self._toggle_token_btn.configure(text="Show Token")
            self._refresh_pairing_display()
            self._set_copy_enabled(True)
        except Exception:  # noqa: BLE001
            self._device_id = None
            self._token = None
            self._set_output(PAIRING_ERROR)
            self._set_copy_enabled(False)
        finally:
            self._gen_btn.configure(state="normal")

    def _revoke_all_generate(self) -> None:
        if not self._on_revoke_all_and_pair:
            return
        self._gen_btn.configure(state="disabled")
        try:
            self._lan_ips = list_lan_ipv4()
            name = normalize_device_name(self._name.get())
            device_id = models.new_id()
            device_id, token = self._on_revoke_all_and_pair(device_id, name)
            self._device_id = device_id
            self._token = token
            self._token_visible = False
            self._toggle_token_btn.configure(text="Show Token")
            self._refresh_pairing_display()
            self._set_copy_enabled(True)
            if self._get_doctor_report:
                self._doctor_label.configure(
                    text=self._doctor_text(bridge_running=True))
        except Exception:  # noqa: BLE001
            self._set_output(PAIRING_ERROR)
            self._set_copy_enabled(False)
        finally:
            self._gen_btn.configure(state="normal")

    def _copy_host(self) -> None:
        host = recommended_lan_ipv4(self._lan_ips)
        if host:
            _copy_to_clipboard(self, host)

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
        self.geometry("680x480")
        ctk.CTkLabel(
            self, text=f"{brand.TERM_MOBILE_ACCESS_RECEIPTS}",
            font=ctk.CTkFont(size=15, weight="bold"),
        ).pack(anchor="w", padx=16, pady=(14, 4))
        ctk.CTkLabel(
            self, text=brand.MOBILE_PROMISE, anchor="w",
            text_color=brand.MUTED_FG, font=ctk.CTkFont(size=11),
        ).pack(anchor="w", padx=16, pady=(0, 8))
        box = CacheVaultTextbox(self, wrap="none")
        box.pack(fill="both", expand=True, padx=12, pady=8)
        if not receipts:
            box.insert("1.0", "No mobile access receipts yet.")
        for r in receipts:
            ts = (r.get("timestamp") or "")[:19].replace("T", " ")
            remote = r.get("remote_ip") or ""
            fix = r.get("suggested_fix") or ""
            line = (
                f"{ts}  {r.get('result','?'):<8}  {r.get('action','?'):<22}  "
                f"{r.get('route','')}  {r.get('device_id') or r.get('device_name') or ''}"
                f"  {remote}  {r.get('reason') or ''}"
            )
            if fix:
                line += f"\n    → {fix}"
            line += "\n"
            box.insert("end", line)
        box.configure(state="disabled")
        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=False)


_DEVICE_STATUS_COLORS = {
    DEVICE_STATUS_ONLINE: brand.PROOF_TEAL,
    DEVICE_STATUS_OFFLINE: brand.MUTED_FG,
    DEVICE_STATUS_WAITING_APPROVAL: brand.STAMP_GOLD,
    DEVICE_STATUS_REVOKED: brand.WARNING_RED,
}


def _device_status_color(status: str) -> str:
    return _DEVICE_STATUS_COLORS.get(status, brand.MUTED_FG)


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
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=12)
        ctk.CTkButton(footer, text="Close", command=self.destroy,
                      **theme.secondary_button()).pack(anchor="e")

        frame = ctk.CTkScrollableFrame(self, height=200)
        frame.pack(side="top", fill="both", expand=True, padx=12, pady=4)
        if not devices:
            ctk.CTkLabel(frame, text="No paired devices yet.",
                         text_color=brand.MUTED_FG).pack(pady=20)
        for d in devices:
            device = PairedDevice.from_dict(d)
            status = paired_device_status(device)
            last_seen = device.last_seen_at or "Never"
            row = ctk.CTkFrame(frame, fg_color="transparent")
            row.pack(fill="x", pady=4)
            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(
                info, text=f"{device.device_name}  ({device.device_id[:8]}…)",
                anchor="w", justify="left",
            ).pack(anchor="w", padx=4)
            ctk.CTkLabel(
                info, text=f"Status: {status}  ·  Last seen: {last_seen}",
                anchor="w", justify="left",
                text_color=_device_status_color(status),
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(anchor="w", padx=4)
            if status != DEVICE_STATUS_REVOKED:
                ctk.CTkButton(
                    row, text="Revoke", width=70,
                    command=lambda i=d["device_id"]: self._revoke(i),
                    **theme.destructive_button(),
                ).pack(side="right", padx=4)

        from .dialogs import _bring_to_front
        _bring_to_front(self, master, modal=True)

    def _revoke(self, device_id: str) -> None:
        self._on_revoke(device_id)
        self.destroy()
