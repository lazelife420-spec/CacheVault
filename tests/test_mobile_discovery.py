"""LAN discovery for Mobile Access bridge."""

from cache_vault.core.mobile.discovery import MobileDiscovery, SERVICE_TYPE


class TestMobileDiscovery:
    def test_not_advertising_by_default(self):
        d = MobileDiscovery()
        assert d.is_advertising is False

    def test_stop_is_safe_when_idle(self):
        MobileDiscovery().stop()

    def test_service_type_constant(self):
        assert "_cachevault-mobile._tcp" in SERVICE_TYPE
