"""Mobile Bridge module manifest.

Thin wrapper around the existing ``cache_vault.core.mobile`` package.
No files are moved; this manifest only declares identity, settings schema,
status rows, and a health check.
"""

from __future__ import annotations

from typing import Any, Callable

from .. import ModuleManifest
from ..settings_schema import SettingsCategory, SettingsField, StatusRow


class MobileBridgeModule(ModuleManifest):
    """Mobile Bridge — LAN read-only API for paired Android devices."""

    def __init__(
        self,
        *,
        bridge_ref: Any | None = None,
        receipts_getter: Callable[[], list[dict]] | None = None,
        mdns_status_getter: Callable[[], bool] | None = None,
    ) -> None:
        self._bridge = bridge_ref
        self._receipts_getter = receipts_getter
        self._mdns_status_getter = mdns_status_getter

    def _bridge_settings(self) -> Any | None:
        """The live ``Settings`` behind ``self._bridge``, or ``None``.

        ``MobileBridge`` exposes its settings via ``bridge.vault.settings``
        (there is no ``bridge._settings`` attribute); this centralizes that
        lookup so status rows and the health check agree on where to find it.
        """
        vault = getattr(self._bridge, "vault", None)
        return getattr(vault, "settings", None) if vault is not None else None

    @property
    def id(self) -> str:
        return "mobile_bridge"

    @property
    def name(self) -> str:
        return "Mobile Bridge"

    @property
    def description(self) -> str:
        return "LAN read-only bridge for paired Android devices"

    @property
    def category(self) -> str:
        return "access"

    # --- settings schema ---

    def get_settings_schema(self) -> list[SettingsCategory]:
        return [
            SettingsCategory(
                id="mobile_bridge", label="Mobile Bridge", icon="\u25C8",
                fields=[
                    SettingsField(
                        "mobile_access_enabled", "Enable Mobile Access", "toggle",
                        "Start the LAN bridge for paired Android devices",
                        group="Connection",
                    ),
                    SettingsField(
                        "mobile_access_port", "Port", "number",
                        "LAN port for the mobile bridge",
                        group="Connection", min_val=1024, max_val=65535,
                    ),
                    SettingsField(
                        "mobile_access_bind_host", "Bind host", "text",
                        "IP to bind (empty = default)",
                        group="Connection",
                    ),
                ],
            ),
        ]

    # --- status rows ---

    def get_status_rows(self) -> list[StatusRow]:
        rows: list[StatusRow] = []

        # Bridge listening status.
        def _bridge_status() -> str:
            if self._bridge is None:
                return "Not started"
            return "Listening" if getattr(self._bridge, "is_running", False) else "Not listening"

        rows.append(StatusRow("Bridge", _bridge_status, level="info"))

        # mDNS advertising.
        def _mdns_status() -> str:
            if self._mdns_status_getter is not None:
                return "Advertising" if self._mdns_status_getter() else "Not advertising"
            return "Unknown"

        rows.append(StatusRow("LAN discovery (mDNS)", _mdns_status, level="info"))

        # Recommended LAN IP.
        def _lan_ip() -> str:
            try:
                from cache_vault.core.lan_ip import recommended_lan_ipv4
                return recommended_lan_ipv4() or "Not detected"
            except Exception:
                return "Not detected"

        rows.append(StatusRow("LAN IP", _lan_ip, level="info"))

        # Last phone request.
        def _last_request() -> str:
            try:
                from cache_vault.core.mobile.connection_doctor import format_last_request
                receipts = self._receipts_getter() if self._receipts_getter else []
                latest = receipts[-1] if receipts else None
                return format_last_request(latest)
            except Exception:
                return "Unknown"

        rows.append(StatusRow("Last phone request", _last_request, level="info"))

        # Paired device count.
        def _paired_count() -> str:
            if self._bridge is None:
                return "Bridge not started"
            settings = self._bridge_settings()
            if settings is not None:
                count = len(getattr(settings, "paired_devices", []))
                return f"{count} paired device{'s' if count != 1 else ''}"
            return "Unknown"

        rows.append(StatusRow("Paired devices", _paired_count, level="info"))

        return rows

    # --- health check ---

    def run_health_check(self) -> dict:
        if self._bridge is None:
            return {"status": "info", "details": "bridge not started"}
        try:
            from cache_vault.core.mobile.connection_doctor import connection_doctor_report
            settings = self._bridge_settings()
            report = connection_doctor_report(
                mobile_access_enabled=getattr(settings, "mobile_access_enabled", False) if settings else False,
                bridge_listening=getattr(self._bridge, "is_running", False),
                port=getattr(settings, "mobile_access_port", 8742) if settings else 8742,
                mdns_advertising=self._mdns_status_getter() if self._mdns_status_getter else False,
            )
            if report["mobile_access"] == "Off":
                return {"status": "warning", "details": "mobile access disabled", "report": report}
            if report["bridge"] != "Listening":
                return {"status": "warning", "details": "bridge not listening", "report": report}
            return {"status": "ok", "details": "bridge running", "report": report}
        except Exception as exc:
            return {"status": "error", "details": str(exc)}
