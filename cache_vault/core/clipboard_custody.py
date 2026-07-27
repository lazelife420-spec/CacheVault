"""Clipboard write custody — keep internal writes out of capture history.

Slice A of the native-acceptance remediation: Cache Vault must never
re-capture its own clipboard writes as new history entries.

Rules implemented here:

* exactly one process-owned :class:`ClipboardWriteSuppressor`, created at the
  application composition root and shared with the monitor and every writer;
* no ``python.exe`` / executable-name exclusion and no foreground-PID-only
  exclusion — custody is proven by explicit records, never process identity;
* thread-safe record access: one lock guards all record state;
* ``time.monotonic()`` deadlines, so wall-clock changes cannot extend or
  shorten custody;
* unique operation tokens with a begin/commit/cancel lifecycle;
* only *committed* records are eligible for suppression;
* every record carries an explicit content type and the exact
  capture-pipeline fingerprint (text: the exact string; image:
  ``models.bytes_hash`` of the PNG bytes — the same hash the monitor computes);
* Windows clipboard sequence-number matching where available;
* one-shot consumption: a matched record is removed immediately;
* shortest measured fallback TTL when sequence access is unavailable;
* failed writes cancel their records;
* once a record is consumed or expires, a later genuine identical copy is
  capturable again.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass

from . import models

#: Suppression window used when clipboard sequence numbers are unavailable on
#: either side. Chosen as the shortest measured bound that still covers the
#: observed write -> WM_CLIPBOARDUPDATE latency on Windows.
DEFAULT_FALLBACK_TTL_S = 0.75

#: Hard upper bound for any record, including sequence-tagged ones. Prevents
#: unbounded record retention if the matching clipboard event never arrives.
MAX_RECORD_TTL_S = 30.0


def default_clipboard_sequence() -> int | None:
    """Current Windows clipboard sequence number, or None when unavailable."""
    try:
        import win32clipboard  # type: ignore

        fn = getattr(win32clipboard, "GetClipboardSequenceNumber", None)
        if fn is not None:
            return int(fn())
    except Exception:  # noqa: BLE001 - clipboard can be transiently locked
        pass
    try:  # ctypes fallback covers pywin32 builds without the wrapper
        import ctypes

        return int(ctypes.windll.user32.GetClipboardSequenceNumber())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001 - non-Windows / API missing
        return None


def _default_set_text(text: str) -> bool:
    from .paste_delivery import set_clipboard_text

    return set_clipboard_text(text)


def _default_restore_text(text: str | None) -> bool:
    from .paste_delivery import restore_clipboard_text

    return restore_clipboard_text(text)


def _default_set_image(png_bytes: bytes) -> bool:
    from .image_assets import write_clipboard_png

    return write_clipboard_png(png_bytes)


@dataclass
class _Record:
    token: str
    operation: str
    content_type: str
    fingerprint: str
    created_at: float
    committed: bool = False
    committed_at: float = 0.0
    sequence: int | None = None


class ClipboardWriteSuppressor:
    """Process-owned registry of committed internal clipboard writes.

    All public methods are safe to call from any thread. Matching consumes
    records one-shot: a record suppresses exactly one clipboard event and is
    removed immediately.
    """

    def __init__(
        self,
        *,
        clock=time.monotonic,
        fallback_ttl: float = DEFAULT_FALLBACK_TTL_S,
        max_ttl: float = MAX_RECORD_TTL_S,
    ) -> None:
        self._clock = clock
        self._fallback_ttl = float(fallback_ttl)
        self._max_ttl = float(max_ttl)
        self._lock = threading.Lock()
        self._records: dict[str, _Record] = {}

    # --- writer lifecycle --------------------------------------------------
    def begin(self, *, operation: str, content_type: str, fingerprint: str) -> str:
        """Open a custody record for an intended write. Returns its token."""
        token = uuid.uuid4().hex
        with self._lock:
            self._purge_locked(self._clock())
            self._records[token] = _Record(
                token=token,
                operation=operation,
                content_type=content_type,
                fingerprint=fingerprint,
                created_at=self._clock(),
            )
        return token

    def commit(self, token: str, *, sequence: int | None = None) -> bool:
        """Mark a begun write as successfully placed on the clipboard."""
        with self._lock:
            rec = self._records.get(token)
            if rec is None or rec.committed:
                return False
            rec.committed = True
            rec.committed_at = self._clock()
            rec.sequence = sequence
            return True

    def cancel(self, token: str) -> bool:
        """Drop a record (failed or abandoned write)."""
        with self._lock:
            return self._records.pop(token, None) is not None

    # --- monitor side --------------------------------------------------------
    def should_suppress(
        self,
        *,
        content_type: str,
        fingerprint: str,
        sequence: int | None = None,
    ) -> bool:
        """Consume and return True when a committed record owns this event."""
        now = self._clock()
        with self._lock:
            self._purge_locked(now)
            for token, rec in self._records.items():
                if not rec.committed or rec.content_type != content_type:
                    continue
                if sequence is not None and rec.sequence is not None:
                    if rec.sequence == sequence:
                        del self._records[token]
                        return True
                    continue
                if now > rec.committed_at + self._fallback_ttl:
                    continue
                if rec.fingerprint == fingerprint:
                    del self._records[token]
                    return True
            return False

    # --- diagnostics / tests -------------------------------------------------
    def snapshot(self) -> list[dict]:
        """Point-in-time view of live records (newest first)."""
        with self._lock:
            self._purge_locked(self._clock())
            return [
                {
                    "token": rec.token,
                    "operation": rec.operation,
                    "content_type": rec.content_type,
                    "committed": rec.committed,
                    "sequence": rec.sequence,
                    "age_s": round(self._clock() - rec.created_at, 6),
                }
                for rec in self._records.values()
            ]

    def __len__(self) -> int:
        with self._lock:
            self._purge_locked(self._clock())
            return len(self._records)

    # --- internals -------------------------------------------------------------
    def _purge_locked(self, now: float) -> None:
        stale = [
            token
            for token, rec in self._records.items()
            if now > rec.created_at + self._max_ttl
            or (rec.committed and now > rec.committed_at + self._max_ttl)
        ]
        for token in stale:
            del self._records[token]


class ClipboardWriter:
    """Custody-enforcing adapter for every internal clipboard write.

    Callers cannot forget custody: ``begin`` runs before the write, and the
    record is either ``commit``-ed (success) or ``cancel``-ed (failure). The
    actual platform write is delegated to ``via`` (per call) or to the
    configured default (Win32-backed), so both UI-thread Tk writes and
    background-thread Win32 writes share the same suppressor.
    """

    def __init__(
        self,
        suppressor: ClipboardWriteSuppressor,
        *,
        set_text=None,
        restore_text=None,
        set_image=None,
        get_sequence=None,
    ) -> None:
        self._suppressor = suppressor
        self._set_text = set_text or _default_set_text
        self._restore_text = restore_text or _default_restore_text
        self._set_image = set_image or _default_set_image
        self._get_sequence = get_sequence or default_clipboard_sequence

    @property
    def suppressor(self) -> ClipboardWriteSuppressor:
        return self._suppressor

    def write_text(self, text: str, *, operation: str, via=None) -> bool:
        """Write ``text`` with custody. ``via`` overrides the write mechanism."""
        write = via or self._set_text
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_TEXT,
            fingerprint=text,
        )
        ok = self._attempt(write, text)
        self._settle(token, ok)
        return ok

    def restore_text(self, text: str | None, *, operation: str, via=None) -> bool:
        """Restore ``text`` with custody (snapshot/restore paste flows)."""
        if text is None:
            return False
        write = via or self._restore_text
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_TEXT,
            fingerprint=text,
        )
        ok = self._attempt(write, text)
        self._settle(token, ok)
        return ok

    def write_image(self, png_bytes: bytes, *, operation: str, via=None) -> bool:
        """Write an image with custody; fingerprint matches the capture hash."""
        write = via or self._set_image
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_IMAGE,
            fingerprint=models.bytes_hash(png_bytes),
        )
        ok = self._attempt(write, png_bytes)
        self._settle(token, ok)
        return ok

    # --- internals ---------------------------------------------------------
    def _attempt(self, write, payload) -> bool:
        try:
            return bool(write(payload))
        except Exception:  # noqa: BLE001 - a failed write must never capture
            return False

    def _settle(self, token: str, ok: bool) -> None:
        if ok:
            self._suppressor.commit(token, sequence=self._sequence())
        else:
            self._suppressor.cancel(token)

    def _sequence(self) -> int | None:
        try:
            return self._get_sequence()
        except Exception:  # noqa: BLE001
            return None
