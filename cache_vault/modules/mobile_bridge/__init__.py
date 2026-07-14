"""Mobile Access module manifest.

Thin wrapper around the existing ``cache_vault.core.mobile`` package.
No files are moved; this manifest only declares identity, settings schema,
status rows, and a health check.
"""

from __future__ import annotations

from typing import Any, Callable

from ... import brand
from .. import ModuleManifest
from ..settings_schema import SettingsCategory, SettingsField, StatusRow


class MobileBridgeModule(ModuleManifest):
    """Mobile Access — LAN read-only API for paired Android devices."""

    def __init__(
        self,
        *,
        bridge_ref: Any | None = None,
        controller_ref: Any | None = None,
        receipts_getter: Callable[[], list[dict]] | None = None,
        mdns_status_getter: Callable[[], bool] | None = None,
        pair_action: Callable[[], None] | None = None,
        devices_action: Callable[[], None] | None = None,
        receipts_action: Callable[[], None] | None = None,
    ) -> None:
        self._bridge = bridge_ref
        self._controller = controller_ref
        self._receipts_getter = receipts_getter
        self._mdns_status_getter = mdns_status_getter
        self._pair_action = pair_action
        self._devices_action = devices_action
        self._receipts_action = receipts_action

    def _bridge_settings(self) -> Any | None:
        """The live ``Settings`` behind ``self._bridge``, or ``None``.

        ``MobileBridge`` exposes its settings via ``bridge.vault.settings``
        (there is no ``bridge._settings`` attribute); this centralizes that
        lookup so status rows and the health check agree on where to find it.
        """
        vault = getattr(self._bridge, "vault", None)
        return getattr(vault, "settings", None) if vault is not None else None

    def _is_enabled(self) -> bool:
        """Canonical enabled state — prefers controller, falls back to settings."""
        if self._controller is not None:
            return bool(getattr(self._controller, "enabled", False))
        settings = self._bridge_settings()
        return bool(getattr(settings, "mobile_access_enabled", False)) if settings else False

    @property
    def id(self) -> str:
        return "mobile_bridge"

    @property
    def name(self) -> str:
        return "Mobile Access"

    @property
    def description(self) -> str:
        return "Phone sync via LAN for paired Android devices"

    @property
    def category(self) -> str:
        return "access"

    # --- settings schema ---

    def get_settings_schema(self) -> list[SettingsCategory]:
        return [
            SettingsCategory(
                id="mobile_bridge", label="Mobile Access", icon="\u25C8",
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
        enabled = self._is_enabled()

        # Phone Sync (formerly "Bridge") status.
        def _bridge_status() -> str:
            if not enabled:
                return "Not running \u2014 Mobile Access is off"
            if self._bridge is None:
                return "Not started"
            if self._controller is not None:
                return "Running" if getattr(self._controller, "listening", False) else "Not running"
            return "Running" if getattr(self._bridge, "is_running", False) else "Not running"

        # Level: "info" when disabled (not red), "ok"/"warning" when enabled
        def _bridge_level() -> str:
            if not enabled:
                return "info"
            is_listening = (
                getattr(self._controller, "listening", False)
                if self._controller is not None
                else getattr(self._bridge, "is_running", False)
            )
            return "ok" if is_listening else "warning"

        rows.append(StatusRow(
            "Phone Sync", _bridge_status, level=_bridge_level(),
            action_label="Pair Android Device" if self._pair_action else "",
            action=self._pair_action,
        ))

        # LAN Discovery (formerly "mDNS") status.
        def _mdns_status() -> str:
            if not enabled:
                return "Not running \u2014 Mobile Access is off"
            if self._controller is not None:
                return "Active" if getattr(self._controller, "advertising", False) else "Not running"
            if self._mdns_status_getter is not None:
                return "Active" if self._mdns_status_getter() else "Not running"
            return "Unknown"

        rows.append(StatusRow(
            "LAN Discovery", _mdns_status,
            level="info" if not enabled else "info",
        ))

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
                from cache_vault.core.mobile.mobile_access_controller import relative_timestamp
                receipts = self._receipts_getter() if self._receipts_getter else []
                latest = receipts[-1] if receipts else None
                if latest and latest.get("timestamp"):
                    rel = relative_timestamp(latest["timestamp"])
                    result = latest.get("result", "")
                    return f"{rel} \u2014 {result}" if result else rel
                return format_last_request(latest)
            except Exception:
                return "Unknown"

        rows.append(StatusRow(
            "Last phone request", _last_request, level="info",
            action_label=brand.TERM_MOBILE_ACCESS_RECEIPTS if self._receipts_action else "",
            action=self._receipts_action,
        ))

        # Paired device count.
        def _paired_count() -> str:
            if self._bridge is None:
                return "Bridge not started"
            settings = self._bridge_settings()
            if settings is not None:
                count = len(getattr(settings, "paired_devices", []))
                return f"{count} paired device{'s' if count != 1 else ''}"
            return "Unknown"

        rows.append(StatusRow(
            "Paired devices", _paired_count, level="info",
            action_label="Paired Devices" if self._devices_action else "",
            action=self._devices_action,
        ))

        return rows

    # --- health check ---

    def run_health_check(self) -> dict:
        if self._bridge is None:
            return {"status": "info", "details": "bridge not started"}
        try:
            from cache_vault.core.mobile.connection_doctor import connection_doctor_report
            settings = self._bridge_settings()

            # Prefer controller state for accuracy
            if self._controller is not None:
                mobile_enabled = self._controller.enabled
                bridge_listening = self._controller.listening
                mdns = self._controller.advertising
            else:
                mobile_enabled = getattr(settings, "mobile_access_enabled", False) if settings else False
                bridge_listening = getattr(self._bridge, "is_running", False)
                mdns = self._mdns_status_getter() if self._mdns_status_getter else False

            report = connection_doctor_report(
                mobile_access_enabled=mobile_enabled,
                bridge_listening=bridge_listening,
                port=getattr(settings, "mobile_access_port", 8742) if settings else 8742,
                mdns_advertising=mdns,
            )
            if report["mobile_access"] == "Off":
                return {"status": "info", "details": "Mobile Access is off", "report": report}
            if report["bridge"] != "Listening":
                return {"status": "warning", "details": "bridge not listening", "report": report}
            return {"status": "ok", "details": "bridge running", "report": report}
        except Exception as exc:
            return {"status": "error", "details": str(exc)}
