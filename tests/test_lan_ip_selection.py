"""list_lan_ipv4()/recommended_lan_ipv4()'s address-selection and ordering.

Found by the E4 design investigation (CACHE_VAULT_E4_LAN_IP_DESIGN_PROPOSAL.md):
this logic had zero dedicated test coverage before this gate (LanIpResolver's
own caching/threading is covered in tests/test_lan_ip_resolver.py; the mDNS
consumer's tier-gate is covered in tests/test_mobile_discovery.py -- but
list_lan_ipv4()'s own ordering, and recommended_lan_ipv4()'s tie-break among
same-tier candidates, were never independently verified in either direction).

Two defects, addressed together (E4a, per the approved design):

1. Same-tier ordering was a plain lexicographic string comparison, not
   numeric -- "192.168.10.1" sorted ahead of "192.168.2.1" because '1' < '2'
   as characters. Fixed by sorting on the actual octet tuple.

2. The outbound-route-preferred address (the getsockname() result from a
   UDP "connect" to 8.8.8.8:80 -- the OS's own answer to "which local IP
   would you use to reach the internet") was computed but then dropped into
   the same unordered set as every other candidate, with no special
   treatment. Two same-tier addresses (e.g. a real Wi-Fi adapter and a
   VMware/VirtualBox host-only adapter, both common on developer machines)
   were then ordered arbitrarily by the string bug above -- a silent
   coin-flip. Fixed by preferring the outbound-preferred address *within
   its own tier* -- it never overrides tier ranking, so a full-tunnel VPN's
   address (which typically resolves to a different, often lower-priority
   or entirely out-of-scope range) cannot become a *new* guaranteed-wrong
   pick that today's arbitrary-but-bounded behavior wouldn't already risk.

Deliberately NOT addressed here (deferred to E4b, if separately authorized):
a VPN client landing in the *same* tier as a genuine physical adapter (e.g.
a corporate VPN issuing a 10.x address while the real LAN is also 10.x) is
not distinguishable by IP-range heuristics alone -- see
test_outbound_preference_does_not_resolve_same_tier_vpn_ambiguity below,
which documents this as an accepted, known limitation rather than silently
passing by accident.
"""

from __future__ import annotations

from unittest import mock

from cache_vault.core import lan_ip


def _mock_candidates(monkeypatch, *, preferred: str | None, others: list[str]):
    """Stand in for list_lan_ipv4()'s two real sources: the outbound-probe
    socket (preferred) and getaddrinfo() (others, plus preferred itself if
    the OS's routing table also surfaces it there, which is common)."""
    class _FakeSocket:
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False
        def connect(self, _addr):
            if preferred is None:
                raise OSError("no route")
        def getsockname(self):
            return (preferred, 0)

    monkeypatch.setattr(lan_ip.socket, "socket", lambda *a, **k: _FakeSocket())
    addrinfo = [(None, None, None, None, (ip, 0)) for ip in others]
    monkeypatch.setattr(lan_ip.socket, "getaddrinfo", lambda *a, **k: addrinfo)


# --- defect 1: numeric, not lexicographic, tie-break -----------------------

def test_same_tier_addresses_sort_numerically_not_lexicographically(monkeypatch):
    """192.168.2.1 must sort before 192.168.10.1 -- neither is the
    outbound-preferred address, isolating the ordering bug from the
    preference-boost feature."""
    _mock_candidates(monkeypatch, preferred=None, others=["192.168.10.1", "192.168.2.1"])
    ips = lan_ip.list_lan_ipv4()
    assert ips == ["192.168.2.1", "192.168.10.1"], ips


# --- defect 2: outbound-preference must win a same-tier coin-flip ----------

def test_outbound_preferred_address_wins_a_same_tier_coin_flip(monkeypatch):
    """The specific bug: two same-tier candidates (e.g. real Wi-Fi vs. a
    VMware host-only adapter), where the outbound-preferred one would have
    lost under plain lexicographic sort. It must now win."""
    _mock_candidates(
        monkeypatch, preferred="192.168.1.50",
        others=["192.168.1.50", "192.168.150.1"],
    )
    assert lan_ip.recommended_lan_ipv4() == "192.168.1.50"


def test_outbound_preference_never_overrides_tier_ranking(monkeypatch):
    """A lower-tier outbound-preferred address must not beat a genuinely
    better-tier candidate -- the preference is a same-tier tie-break only,
    never a tier override."""
    _mock_candidates(
        monkeypatch, preferred="172.20.0.5",
        others=["172.20.0.5", "192.168.1.10"],
    )
    assert lan_ip.recommended_lan_ipv4() == "192.168.1.10"


def test_out_of_tier_outbound_preference_does_not_win_at_all(monkeypatch):
    """Simulates a full-tunnel VPN scenario: the outbound probe resolves to
    an address outside every preferred tier. The recommendation must fall
    back to the best real in-tier candidate -- not the out-of-tier
    outbound-preferred address. This is the acceptance criterion (G in the
    design doc) that a naive unconditional preference would have violated."""
    _mock_candidates(
        monkeypatch, preferred="100.64.0.7",
        others=["100.64.0.7", "192.168.1.10"],
    )
    assert lan_ip.recommended_lan_ipv4() == "192.168.1.10"


def test_outbound_preference_does_not_resolve_same_tier_vpn_ambiguity(monkeypatch):
    """Documented, accepted E4a limitation, not a silent gap: a VPN address
    that happens to land in the SAME tier as a genuine physical adapter
    (e.g. a corporate VPN issuing 10.x while the real LAN is also 10.x) is
    not distinguishable from the real adapter by IP-range heuristics alone.
    Whichever of the two is the outbound-preferred one wins this specific
    ambiguous case -- by design, since the outbound-preferred signal really
    is what the OS itself would route through, and there is no way to know
    from this test's numeric-vs-lexicographic/tier scope whether that is
    "correct" here. Deferred to E4b (interface-type discrimination)."""
    _mock_candidates(
        monkeypatch, preferred="10.8.0.2",  # simulated VPN-issued address
        others=["10.8.0.2", "10.0.0.15"],   # simulated real LAN address, same tier
    )
    # Whichever wins, it must be deterministic and in-tier -- not a crash,
    # not an out-of-tier pick. The specific winner here is the documented,
    # accepted limitation, not asserted as "correct" for this scenario.
    result = lan_ip.recommended_lan_ipv4()
    assert result in ("10.8.0.2", "10.0.0.15")
    assert result == "10.8.0.2", (
        "outbound-preference wins the same-tier VPN-ambiguity case by "
        "design in E4a -- this is the accepted limitation, not a bug"
    )


# --- no regression to already-correct cases ---------------------------------

def test_single_adapter_unchanged(monkeypatch):
    _mock_candidates(monkeypatch, preferred="192.168.1.5", others=["192.168.1.5"])
    assert lan_ip.recommended_lan_ipv4() == "192.168.1.5"


def test_real_wifi_still_beats_lower_tier_hyperv_adapter(monkeypatch):
    _mock_candidates(
        monkeypatch, preferred="192.168.1.5",
        others=["192.168.1.5", "172.28.32.1"],
    )
    assert lan_ip.recommended_lan_ipv4() == "192.168.1.5"


def test_no_addresses_detected_returns_none(monkeypatch):
    _mock_candidates(monkeypatch, preferred=None, others=[])
    assert lan_ip.list_lan_ipv4() == []
    assert lan_ip.recommended_lan_ipv4() is None


# --- unification: QR path and mDNS path now agree, by construction --------

def test_qr_and_mdns_paths_recommend_the_same_address_for_the_same_candidates(monkeypatch):
    """bridge.py::create_pairing_offer and discovery.py::_lan_addresses both
    call recommended_lan_ipv4(list_lan_ipv4()) -- fixing the shared root
    means both inherit the same, now-deterministic answer automatically,
    with no separate policy-porting code needed in either consumer."""
    _mock_candidates(
        monkeypatch, preferred="192.168.1.50",
        others=["192.168.1.50", "192.168.150.1"],
    )
    from cache_vault.core.mobile.discovery import _lan_addresses
    import socket as real_socket

    qr_pick = lan_ip.recommended_lan_ipv4(lan_ip.list_lan_ipv4())
    mdns_addrs = [real_socket.inet_ntoa(a) for a in _lan_addresses()]

    assert qr_pick == "192.168.1.50"
    assert mdns_addrs == ["192.168.1.50"]
