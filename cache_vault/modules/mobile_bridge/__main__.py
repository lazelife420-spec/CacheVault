"""Standalone Mobile Bridge Doctor launcher.

Usage:
    python -m cache_vault.modules.mobile_bridge           # show connection doctor report
    python -m cache_vault.modules.mobile_bridge --selftest # headless sanity check
"""

from __future__ import annotations

import sys


def _selftest() -> int:
    """Headless sanity check for Mobile Bridge module."""
    try:
        from cache_vault.core.mobile.connection_doctor import connection_doctor_report
        from cache_vault.modules.mobile_bridge import MobileBridgeModule

        # Test manifest properties
        module = MobileBridgeModule()
        assert module.id == "mobile_bridge"
        assert "Mobile Access" in module.name

        # Test doctor report generation (mocked inputs)
        report = connection_doctor_report(
            mobile_access_enabled=True,
            bridge_listening=False,
            port=8742,
            mdns_advertising=False,
        )
        assert report["mobile_access"] == "On"
        assert report["bridge"] == "Not listening"

        # Test module health check
        health = module.run_health_check()
        assert health["status"] in ("ok", "warning", "info", "error")

        print("mobile_bridge selftest OK")
        return 0
    except Exception as exc:
        print(f"mobile_bridge selftest FAILED: {exc}")
        return 1


def main() -> int:
    if "--selftest" in sys.argv:
        return _selftest()

    try:
        from cache_vault.core.mobile.connection_doctor import (
            connection_doctor_report,
            connection_doctor_text,
        )
        from cache_vault.core.settings import Settings

        settings = Settings.load()
        # Note: In a real standalone run, we don't have a live bridge reference
        # unless we start one, but the Doctor is meant to report on the current
        # configuration and last known state.
        report = connection_doctor_report(
            mobile_access_enabled=settings.mobile_access_enabled,
            bridge_listening=False,  # Standalone doctor doesn't start the bridge
            port=settings.mobile_access_port,
            bind_host=settings.mobile_access_bind_host,
            mdns_advertising=False,
        )

        print("--- Cache Vault Mobile Access Doctor ---")
        print(connection_doctor_text(report))
        print("---------------------------------------")
        print("Note: Bridge status is 'Not listening' because this is the standalone doctor.")
        return 0
    except Exception as exc:
        print(f"Error running Mobile Bridge Doctor: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
