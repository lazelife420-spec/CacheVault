"""MobileAccessController — single authoritative state controller.

Every UI surface (toolbar, Settings Hub, Mobile Access page, pairing dialog,
diagnostics, tray) subscribes to this controller instead of independently
querying ``settings.mobile_access_enabled`` or ``bridge.is_running``.

State changes are transactional: enable persists, starts, verifies, advertises,
and notifies — or rolls back completely.  Disable stops mDNS, stops the
listener, persists, verifies, and notifies.
"""

from __future__ import annotations

import logging
import socket
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Callable

from .models import DEFAULT_BIND_HOST, DEFAULT_MOBILE_PORT

if TYPE_CHECKING:
    from ..settings import Settings
    from .bridge import MobileBridge

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MobileAccessState:
    """Immutable snapshot of the canonical mobile-access state."""

    enabled: bool
    listening: bool
    advertising: bool
    port: int
    bind_host: str
    paired_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class EnableResult:
    """Outcome of a transactional ``enable()`` call."""

    success: bool
    error: str | None = None
    port: int = 0
    bind_host: str = ""


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------

class MobileAccessController:
    """Single source of truth for Mobile Access state.

    **Invariants enforced:**

    * *Disabled* → no listener, no mDNS advertisement, no accepted requests.
    * *Enabled* → listener active, mDNS advertising, state persisted.
    * All state queries go through this controller.
    * All state changes go through this controller.
    """

    def __init__(self, vault, bridge: MobileBridge) -> None:
        self._vault = vault
        self._bridge = bridge
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[MobileAccessState], None]] = []
        self._last_error: str | None = None

    # -- Canonical read-only state -----------------------------------------

    @property
    def enabled(self) -> bool:
        """Whether Mobile Access is currently enabled (persisted setting)."""
        return bool(self._vault.settings.mobile_access_enabled)

    @property
    def listening(self) -> bool:
        """Whether the HTTP bridge listener is accepting connections."""
        return self._bridge.is_running

    @property
    def advertising(self) -> bool:
        """Whether mDNS / Bonjour is broadcasting on the LAN."""
        return self._bridge.discovery.is_advertising

    @property
    def healthy(self) -> bool:
        """Fully operational: enabled AND listening AND advertising."""
        return self.enabled and self.listening and self.advertising

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def status_text(self) -> str:
        """Human-readable status for all UI surfaces."""
        if not self.enabled:
            return "Off"
        if not self.listening:
            return f"Error — not listening ({self._last_error or 'unknown'})"
        if not self.advertising:
            return "On — LAN discovery unavailable"
        return "On"

    def state_snapshot(self) -> MobileAccessState:
        """Current canonical state for subscribers and UI."""
        settings = self._vault.settings
        return MobileAccessState(
            enabled=self.enabled,
            listening=self.listening,
            advertising=self.advertising,
            port=int(settings.mobile_access_port or DEFAULT_MOBILE_PORT),
            bind_host=(settings.mobile_access_bind_host or DEFAULT_BIND_HOST).strip(),
            paired_count=len(settings.paired_devices),
            error=self._last_error,
        )

    # -- Transactional state changes ---------------------------------------

    def enable(self, settings: Settings) -> EnableResult:
        """Persist desired_enabled=True → try to start bridge → verify.

        If starting fails, we do NOT revert settings.mobile_access_enabled to False.
        Instead, we keep it True so the user's intent is preserved, but we update
        the controller's runtime state to represent the error, populate last_error,
        and return success=False.
        """
        with self._lock:
            host = (settings.mobile_access_bind_host or DEFAULT_BIND_HOST).strip()
            port = int(settings.mobile_access_port or DEFAULT_MOBILE_PORT)

            # 1. Persist (desired_enabled = True)
            settings.mobile_access_enabled = True
            settings.save()

            # If already running on correct host/port, do not restart
            if self._bridge.is_running and self._bridge._listen_host == host and self._bridge._listen_port == port: # noqa: SLF001
                self._last_error = None
                self._notify()
                return EnableResult(success=True, port=port, bind_host=host)

            # 2. (Re)start bridge
            self._bridge.stop()
            started = self._bridge._start(host, port)  # noqa: SLF001
            if not started:
                self._last_error = f"Port {port} is already in use."
                self._notify()
                return EnableResult(success=False,
                                    error=f"Could not start Mobile Access.\n"
                                          f"Port {port} is already in use.",
                                    port=port, bind_host=host)

            # 3. Verify listener
            if not self._bridge.is_running:
                self._bridge.stop()
                self._last_error = "Mobile Access listener failed to start."
                self._notify()
                return EnableResult(success=False,
                                    error="Mobile Access listener failed to start.",
                                    port=port, bind_host=host)

            # 4. Start mDNS (best-effort; failure is non-fatal)
            mdns_ok = False
            try:
                host_name = socket.gethostname()
                mdns_ok = self._bridge.discovery.start(port, pc_name=host_name)
            except Exception:  # noqa: BLE001
                log.debug("mDNS start failed (non-fatal)")

            self._last_error = None
            self._notify()
            return EnableResult(success=True, port=port, bind_host=host)

    def disable(self, settings: Settings) -> None:
        """Stop mDNS → stop listener → persist → verify → notify."""
        with self._lock:
            # 1. Stop mDNS first (no more advertisements)
            try:
                self._bridge.discovery.stop()
            except Exception:  # noqa: BLE001
                pass

            # 2. Stop HTTP listener
            self._bridge.stop()

            # 3. Persist
            settings.mobile_access_enabled = False
            settings.save()

            # 4. Verify (defense-in-depth)
            if self._bridge.is_running:
                log.warning("Bridge still running after disable — force-stopping")
                self._bridge.stop()

            self._last_error = None
            self._notify()

    def sync(self, settings: Settings) -> None:
        """Align runtime state to persisted settings (used on startup).

        If settings say enabled, starts the bridge.  If disabled, ensures
        nothing is running.
        """
        if settings.mobile_access_enabled:
            if not self._bridge.is_running:
                self.enable(settings)
        else:
            if self._bridge.is_running or self._bridge.discovery.is_advertising:
                self.disable(settings)
            else:
                self._notify()

    def needs_change(self, settings: Settings) -> bool:
        """True when the runtime state doesn't match what *settings* wants."""
        want = bool(settings.mobile_access_enabled)
        if want != self._bridge.is_running:
            return True
        if want:
            host = (settings.mobile_access_bind_host or DEFAULT_BIND_HOST).strip()
            port = int(settings.mobile_access_port or DEFAULT_MOBILE_PORT)
            if (self._bridge._listen_host != host or   # noqa: SLF001
                    self._bridge._listen_port != port):  # noqa: SLF001
                return True
        return False

    def restart(self, settings: Settings) -> EnableResult:
        """Stop and re-enable.  Useful for port/host changes."""
        self.disable(settings)
        settings.mobile_access_enabled = True
        return self.enable(settings)

    # -- Subscriber pattern ------------------------------------------------

    def subscribe(self, callback: Callable[[MobileAccessState], None]) -> None:
        """Register a listener that is called on every state change."""
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[MobileAccessState], None]) -> None:
        try:
            self._subscribers.remove(callback)
        except ValueError:
            pass

    def _notify(self) -> None:
        snapshot = self.state_snapshot()
        for cb in list(self._subscribers):
            try:
                cb(snapshot)
            except Exception:  # noqa: BLE001 — subscriber errors must not block
                log.debug("Subscriber error", exc_info=True)


# ---------------------------------------------------------------------------
# Utility: human-friendly relative timestamps
# ---------------------------------------------------------------------------

def relative_timestamp(iso: str | None) -> str:
    """Convert an ISO timestamp to a human-friendly relative string.

    Returns ``"Just now"``, ``"2 minutes ago"``, ``"3 hours ago"``, etc.
    Falls back to truncated ISO if parsing fails.
    """
    if not iso:
        return "Never"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        seconds = delta.total_seconds()
        if seconds < 0:
            return "Just now"
        if seconds < 60:
            return "Just now"
        if seconds < 3600:
            mins = int(seconds // 60)
            return f"{mins} minute{'s' if mins != 1 else ''} ago"
        if seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours} hour{'s' if hours != 1 else ''} ago"
        days = int(seconds // 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    except Exception:  # noqa: BLE001
        return iso[:19].replace("T", " ") if len(iso) >= 19 else iso
