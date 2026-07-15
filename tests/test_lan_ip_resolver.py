"""Tests for LanIpResolver — the deadline-bounded, background LAN IP lookup.

These exist because the old code called ``socket.getaddrinfo`` directly and
synchronously from the Settings Hub's Tk-thread render path: an untimed DNS
call that can hang far longer than any UI should block, freezing the whole
app (not just the Settings window, since Tk is single-threaded). The
resolver must never let its caller block, must cache successful results,
must give up on a deadline rather than hang forever, and must not spawn a
second concurrent lookup while one is already running.
"""

from __future__ import annotations

import threading
import time

from cache_vault.core import lan_ip as lan_ip_module
from cache_vault.core.lan_ip import (
    PENDING_TEXT,
    UNAVAILABLE_TEXT,
    LanIpResolver,
)


def test_status_text_never_blocks_the_caller(monkeypatch):
    """The very first call must return immediately, even though resolution
    hasn't happened yet — it must never call socket/getaddrinfo inline."""
    started = threading.Event()
    release = threading.Event()

    def slow_lookup():
        started.set()
        release.wait(timeout=5)
        return ["192.168.1.50"]

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", slow_lookup)
    resolver = LanIpResolver(deadline=5.0)

    t0 = time.monotonic()
    text = resolver.status_text()
    elapsed = time.monotonic() - t0

    assert text == PENDING_TEXT
    assert elapsed < 1.0, "status_text() must not block on the resolver"
    assert started.wait(timeout=2), "background lookup never started"

    release.set()  # let the worker finish so it doesn't leak past the test


def test_successful_resolution_is_cached_and_reported(monkeypatch):
    ready = threading.Event()

    def fast_lookup():
        ready.set()
        return ["10.0.0.7"]

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", fast_lookup)
    resolver = LanIpResolver(deadline=5.0)

    resolver.status_text()  # kicks off the background thread
    assert ready.wait(timeout=2)
    # Give the worker a moment to write the cache after returning.
    deadline = time.monotonic() + 2
    while resolver.is_pending() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert resolver.status_text() == "10.0.0.7"
    assert resolver.is_pending() is False


def test_resolver_exception_reports_not_detected_not_pending(monkeypatch):
    def boom():
        raise OSError("network unreachable")

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", boom)
    resolver = LanIpResolver(deadline=5.0)

    resolver.status_text()  # starts the (immediately-failing) lookup
    deadline = time.monotonic() + 2
    while resolver.is_pending() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert resolver.is_pending() is False
    assert resolver.status_text() == "Not detected"


def test_missed_deadline_falls_back_without_waiting_forever(monkeypatch):
    def very_slow_lookup():
        time.sleep(0.3)
        return ["172.16.0.4"]

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", very_slow_lookup)
    resolver = LanIpResolver(deadline=0.05)

    first = resolver.status_text()
    assert first in (PENDING_TEXT, UNAVAILABLE_TEXT)

    time.sleep(0.15)  # now well past the 0.05s deadline, thread still running
    assert resolver.status_text() == UNAVAILABLE_TEXT

    # The late result still lands in the cache once it finally arrives, so a
    # later read (e.g. the user re-opens Settings) self-corrects instead of
    # being stuck on "Could not detect" forever.
    time.sleep(0.3)
    assert resolver.status_text() == "172.16.0.4"


def test_reset_discards_a_late_result(monkeypatch):
    """Simulates the Settings window closing / view changing while a lookup
    is still in flight: reset() must make the eventually-arriving result a
    no-op rather than overwrite the cache."""
    def slow_lookup():
        time.sleep(0.15)
        return ["1.2.3.4"]

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", slow_lookup)
    resolver = LanIpResolver(deadline=5.0)

    resolver.status_text()  # starts the lookup under generation 1
    resolver.reset()  # e.g. window closed — bumps generation, clears cache

    time.sleep(0.3)  # let the stale lookup finish and try to write back

    assert resolver._cached_ips is None, "a superseded lookup must not repopulate the cache"


def test_repeated_calls_do_not_start_duplicate_lookups(monkeypatch):
    call_count = {"n": 0}
    release = threading.Event()

    def slow_lookup():
        call_count["n"] += 1
        release.wait(timeout=5)
        return ["9.9.9.9"]

    monkeypatch.setattr(lan_ip_module, "list_lan_ipv4", slow_lookup)
    resolver = LanIpResolver(deadline=5.0)

    for _ in range(10):
        resolver.status_text()
        resolver.is_pending()

    release.set()
    deadline = time.monotonic() + 2
    while resolver.is_pending() and time.monotonic() < deadline:
        time.sleep(0.01)

    assert call_count["n"] == 1, "repeated status reads must not spawn concurrent lookups"
