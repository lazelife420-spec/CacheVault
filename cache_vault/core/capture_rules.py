"""Capture rule state — armed next-copy and ignore-next-copy modes."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from .safes import SAFE_DEFAULT, SafeRegistry


ARM_TIMEOUT_SEC = 60
IGNORE_TIMEOUT_SEC = 60


@dataclass
class ArmedCapture:
    safe_id: str
    safe_name: str
    armed_at: float


class CaptureController:
    """Tracks one-shot armed/ignore modes for clipboard capture."""

    def __init__(self, settings_getter: Callable[[], object]):
        self._get_settings = settings_getter
        self._armed: ArmedCapture | None = None
        self._ignore_next = False
        self._ignore_at: float | None = None

    def _now(self) -> float:
        return time.monotonic()

    def _expire_stale(self) -> None:
        now = self._now()
        if self._armed and now - self._armed.armed_at > ARM_TIMEOUT_SEC:
            self._armed = None
        if self._ignore_next and self._ignore_at is not None:
            if now - self._ignore_at > IGNORE_TIMEOUT_SEC:
                self._ignore_next = False
                self._ignore_at = None

    @property
    def armed(self) -> ArmedCapture | None:
        self._expire_stale()
        return self._armed

    @property
    def ignore_next(self) -> bool:
        self._expire_stale()
        return self._ignore_next

    def arm_next_copy(self, safe_id: str, safe_name: str) -> None:
        self._ignore_next = False
        self._ignore_at = None
        self._armed = ArmedCapture(safe_id, safe_name, self._now())

    def arm_ignore_next(self) -> None:
        self._armed = None
        self._ignore_next = True
        self._ignore_at = self._now()

    def cancel_armed(self) -> None:
        self._armed = None

    def cancel_ignore(self) -> None:
        self._ignore_next = False
        self._ignore_at = None

    def cancel_all(self) -> None:
        self.cancel_armed()
        self.cancel_ignore()

    def consume_ignore(self) -> bool:
        """Return True if this clipboard change should be skipped."""
        self._expire_stale()
        if not self._ignore_next:
            return False
        self._ignore_next = False
        self._ignore_at = None
        return True

    def consume_armed(self) -> tuple[str, str] | None:
        """Return (safe_id, safe_name) once for the next capture, then clear."""
        self._expire_stale()
        if self._armed is None:
            return None
        sid, name = self._armed.safe_id, self._armed.safe_name
        self._armed = None
        return sid, name

    def should_auto_capture(self) -> bool:
        settings = self._get_settings()
        if getattr(settings, "capture_paused", False):
            return False
        return bool(getattr(settings, "auto_capture_enabled", True))

    def resolve_safe_for_auto(self) -> tuple[str, str]:
        reg = SafeRegistry(self._get_settings())
        safe = reg.default_safe()
        return safe.id, safe.name

    def pick_safe_for_manual(self) -> tuple[str, str] | None:
        """Default safe when picker is off; None means UI should show picker."""
        settings = self._get_settings()
        reg = SafeRegistry(settings)
        if getattr(settings, "show_safe_picker_on_manual_save", False):
            return None
        safe = reg.default_safe()
        if reg.is_ignore(safe.id):
            safe = reg.resolve(SAFE_DEFAULT) or reg.builtin_safes()[0]
        return safe.id, safe.name
