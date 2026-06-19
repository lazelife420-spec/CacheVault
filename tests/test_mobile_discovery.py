"""LAN discovery for Mobile Access bridge."""

import socket

from cache_vault.core import lan_ip as lan_ip_mod
from cache_vault.core.mobile.discovery import MobileDiscovery, SERVICE_TYPE, _lan_addresses


class TestMobileDiscovery:
    def test_not_advertising_by_default(self):
        d = MobileDiscovery()
        assert d.is_advertising is False

    def test_stop_is_safe_when_idle(self):
        MobileDiscovery().stop()

    def test_service_type_constant(self):
        assert "_cachevault._tcp" in SERVICE_TYPE

    def test_service_type_label_is_mdns_compliant(self):
        """mDNS application-protocol label must be <= 15 bytes (RFC 6763)."""
        label = SERVICE_TYPE.split("._tcp")[0].lstrip("_")
        assert len(label.encode("utf-8")) <= 15, label

    def test_lan_addresses_advertise_only_reachable_wifi_ip(self, monkeypatch):
        """Advertise only the recommended Wi-Fi LAN IP on a multi-homed PC.

        mDNS does not preserve A-record order and Android's NsdManager resolves a
        single host; advertising Hyper-V/WSL 172.x adapters too can make the phone
        resolve an unreachable PC ("No PC found"). A single reachable address is
        unambiguous.
        """
        monkeypatch.setattr(
            lan_ip_mod,
            "list_lan_ipv4",
            lambda: ["172.25.240.1", "172.21.32.1", "192.168.0.11", "172.30.128.1"],
        )
        addrs = [socket.inet_ntoa(a) for a in _lan_addresses()]
        assert addrs == ["192.168.0.11"]

    def test_lan_addresses_fall_back_to_all_when_no_home_lan(self, monkeypatch):
        """With no 192.168.x/10.x IP, advertise all detected addresses."""
        monkeypatch.setattr(
            lan_ip_mod,
            "list_lan_ipv4",
            lambda: ["172.20.10.5", "172.21.32.1"],
        )
        addrs = [socket.inet_ntoa(a) for a in _lan_addresses()]
        assert set(addrs) == {"172.20.10.5", "172.21.32.1"}

    def test_lan_addresses_empty_when_no_ips(self, monkeypatch):
        monkeypatch.setattr(lan_ip_mod, "list_lan_ipv4", lambda: [])
        assert _lan_addresses() == []
