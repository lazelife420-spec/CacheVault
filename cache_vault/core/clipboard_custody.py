"""Clipboard write custody — keep internal writes out of capture history.

Slice A of the native-acceptance remediation: Cache Vault must never
re-capture its own clipboard writes as new history entries.

Rules implemented here:

* exactly one process-owned :class:`ClipboardWriteSuppressor`, created at the
  application composition root and shared with the monitor and every writer;
* no ``python.exe`` / executable-name exclusion and no foreground-PID-only
  exclusion — custody is proven by explicit records, never process identity;
* thread-safe record access: one condition guards all record state;
* ``time.monotonic()`` deadlines, so wall-clock changes cannot extend or
  shorten custody;
* unique operation tokens with a begin/commit/cancel lifecycle;
* pending records are not automatically suppressive, but matching observers may
  wait for the exact token to settle;
* every record carries an explicit content type and the exact
  capture-pipeline fingerprint (text: the canonical-CRLF string a reader will
  actually see on the clipboard -- not necessarily the caller's raw input,
  since every writer (Tk or raw Win32) normalizes line breaks before the
  platform write; image: the canonical RGB pixel fingerprint shared with the
  monitor);
* Windows clipboard sequence-number matching where available, treated as an
  unsigned 32-bit counter;
* one-shot consumption: a matched record is removed immediately;
* fallback TTL derived from the active monitor mode and measured cadence;
* failed writes cancel their records;
* once a record is consumed or expires, a later genuine identical copy is
  capturable again.
"""

from __future__ import annotations

import enum
import logging
import threading
import time
import uuid
from dataclasses import dataclass
from typing import NamedTuple

from . import models
from .image_assets import canonical_image_fingerprint

logger = logging.getLogger(__name__)

#: Default monitor polling interval used when pywin32 is unavailable.
DEFAULT_MONITOR_POLL_INTERVAL_MS = 800
DEFAULT_MONITOR_POLL_INTERVAL_S = DEFAULT_MONITOR_POLL_INTERVAL_MS / 1000.0

#: ClipboardMonitor clamps configured polling to at least 200ms.  Use that
#: same validated floor when deriving a fallback lifetime directly.
MIN_MONITOR_POLL_INTERVAL_S = 0.2

#: Measured scheduling margin for polling fallback.  Covers worst-case jitter
#: between an internal write and the next poll detection on a loaded host.
#: See qa_artifacts/clipboard-custody-correction/polling-latency.tsv.
POLLING_FALLBACK_MARGIN_S = 0.25

#: Event-listener (WM_CLIPBOARDUPDATE) delivery is sub-millisecond on a healthy
#: Windows desktop.  This bound covers scheduler jitter when sequences are
#: unavailable.
EVENT_FALLBACK_LATENCY_S = 0.01
EVENT_FALLBACK_MARGIN_S = 0.05

#: Suppression window used when clipboard sequence numbers are unavailable on
#: either side.  For polling mode this must cover the configured poll interval
#: plus measured jitter; the default corresponds to the 800ms polling cadence.
DEFAULT_FALLBACK_TTL_S = DEFAULT_MONITOR_POLL_INTERVAL_S + POLLING_FALLBACK_MARGIN_S

#: How long a matching observer may wait for a pending record to settle.
#: Derived from the slowest measured platform clipboard write (text/image)
#: plus a bounded safety margin.  See evidence/clipboard-write-latency.tsv.
PENDING_SETTLEMENT_TIMEOUT_S = 0.2

#: Hard upper bound for any record, including sequence-tagged ones. Prevents
#: unbounded record retention if the matching clipboard event never arrives.
MAX_RECORD_TTL_S = 30.0


class SuppressionDecision(enum.Enum):
    """Explicit custody verdict returned by the decider."""

    SUPPRESS = "suppress"
    CAPTURE = "capture"
    WAIT = "wait"


def default_clipboard_sequence() -> int | None:
    """Current Windows clipboard sequence number, or None when unavailable.

    Microsoft documents this as an unsigned 32-bit counter incremented each
    time the clipboard owner changes.  pywin32 exposes it through
    ``win32clipboard.GetClipboardSequenceNumber`` (build 227 and later).  Older
    pywin32 builds or non-Windows environments fall back to
    ``ctypes.windll.user32.GetClipboardSequenceNumber``.  When the API cannot
    be reached the value is ``None`` and custody falls back to the canonical
    fingerprint within the bounded fallback window.
    """
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


def _default_set_text(text: str):
    # Returns paste_delivery.ClipboardWriteOutcome (or None) rather than a
    # plain bool -- ClipboardWriter._attempt() unpacks it to distinguish
    # custody-commit from user-visible success. See ClipboardWriteOutcome.
    from .paste_delivery import _set_clipboard_text_outcome

    return _set_clipboard_text_outcome(text)


def _default_restore_text(text: str | None):
    from .paste_delivery import _restore_clipboard_text_outcome

    return _restore_clipboard_text_outcome(text)


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
    sequence_before: int | None = None
    sequence_after: int | None = None


class ClipboardWriteSuppressor:
    """Process-owned registry of internal clipboard writes.

    All public methods are safe to call from any thread. Matching consumes
    records one-shot: a record suppresses exactly one clipboard event and is
    removed immediately.  A matching observer may briefly wait for a pending
    record to settle, but the condition wait always releases the internal lock,
    and the lock is never held across the actual platform clipboard call.
    """

    def __init__(
        self,
        *,
        clock=time.monotonic,
        fallback_ttl: float | None = None,
        pending_timeout: float = PENDING_SETTLEMENT_TIMEOUT_S,
        max_ttl: float = MAX_RECORD_TTL_S,
    ) -> None:
        self._clock = clock
        self._fallback_ttl = (
            float(fallback_ttl) if fallback_ttl is not None else DEFAULT_FALLBACK_TTL_S
        )
        self._pending_timeout = float(pending_timeout)
        self._max_ttl = float(max_ttl)
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._records: dict[str, _Record] = {}

    # --- writer lifecycle --------------------------------------------------
    def begin(self, *, operation: str, content_type: str, fingerprint: str) -> str:
        """Open a custody record for an intended write. Returns its token."""
        token = uuid.uuid4().hex
        with self._condition:
            self._purge_locked(self._clock())
            self._records[token] = _Record(
                token=token,
                operation=operation,
                content_type=content_type,
                fingerprint=fingerprint,
                created_at=self._clock(),
            )
        return token

    def commit(
        self,
        token: str,
        *,
        sequence: int | None = None,
        sequence_before: int | None = None,
        sequence_after: int | None = None,
    ) -> bool:
        """Mark a begun write as successfully placed on the clipboard."""
        with self._condition:
            rec = self._records.get(token)
            if rec is None or rec.committed:
                return False
            if sequence_after is None:
                sequence_after = sequence
            rec.committed = True
            rec.committed_at = self._clock()
            rec.sequence_before = sequence_before
            rec.sequence_after = sequence_after
            self._condition.notify_all()
            return True

    def cancel(self, token: str) -> bool:
        """Drop a record (failed or abandoned write) and wake its waiters."""
        with self._condition:
            existed = self._records.pop(token, None) is not None
            if existed:
                self._condition.notify_all()
            return existed

    # --- monitor side --------------------------------------------------------
    def should_suppress(
        self,
        *,
        content_type: str,
        fingerprint: str,
        sequence: int | None = None,
    ) -> bool:
        """Consume and return True when the matching record owns this event."""
        return (
            self.decide(
                content_type=content_type,
                fingerprint=fingerprint,
                sequence=sequence,
            )
            is SuppressionDecision.SUPPRESS
        )

    def decide(
        self,
        *,
        content_type: str,
        fingerprint: str,
        sequence: int | None = None,
    ) -> SuppressionDecision:
        """Return an explicit :class:`SuppressionDecision` for the event.

        A matching pending record causes a bounded wait; the condition wait
        releases the internal lock, so a concurrent writer can complete its
        platform call and commit/cancel without being blocked.
        """
        now = self._clock()
        deadline = now + self._pending_timeout
        with self._condition:
            while True:
                now = self._clock()
                self._purge_locked(now)
                decision, token = self._evaluate_locked(
                    content_type=content_type,
                    fingerprint=fingerprint,
                    sequence=sequence,
                    now=now,
                )
                if decision is not SuppressionDecision.WAIT:
                    if decision is SuppressionDecision.SUPPRESS:
                        del self._records[token]
                    return decision
                # Wait for the specific token to settle.
                rec = self._records.get(token)
                if rec is None:
                    # Cancelled/removed between scan and wait.
                    return SuppressionDecision.CAPTURE
                remaining = deadline - self._clock()
                if remaining <= 0:
                    self._diagnostic(
                        "pending_settlement_timeout",
                        rec=rec,
                        content_type=content_type,
                        fingerprint=fingerprint,
                        sequence=sequence,
                    )
                    # Abandon the exact pending operation atomically.  A slow
                    # writer that eventually returns cannot commit this token
                    # and make it suppressive again.
                    current = self._records.get(token)
                    if current is rec and not current.committed:
                        del self._records[token]
                        self._condition.notify_all()
                    return SuppressionDecision.CAPTURE
                self._condition.wait(timeout=remaining)

    def set_monitor_cadence(
        self,
        *,
        mode: str,
        cadence_s: float,
    ) -> None:
        """Derive the fallback TTL from the active monitor mode and cadence.

        Polling fallback must cover the configured interval plus measured
        scheduling jitter.  Event-listener fallback only needs to cover the
        small delivery bound plus scheduler jitter.
        """
        with self._condition:
            if mode == "event":
                ttl = EVENT_FALLBACK_LATENCY_S + EVENT_FALLBACK_MARGIN_S
            else:
                ttl = (
                    max(float(cadence_s), MIN_MONITOR_POLL_INTERVAL_S)
                    + POLLING_FALLBACK_MARGIN_S
                )
            self._fallback_ttl = float(ttl)

    # --- diagnostics / tests -------------------------------------------------
    def snapshot(self) -> list[dict]:
        """Point-in-time view of live records (newest first)."""
        with self._condition:
            self._purge_locked(self._clock())
            return [
                {
                    "token": rec.token,
                    "operation": rec.operation,
                    "content_type": rec.content_type,
                    "committed": rec.committed,
                    "sequence": rec.sequence_after,
                    "sequence_before": rec.sequence_before,
                    "sequence_after": rec.sequence_after,
                    "age_s": round(self._clock() - rec.created_at, 6),
                }
                for rec in self._records.values()
            ]

    def __len__(self) -> int:
        with self._condition:
            self._purge_locked(self._clock())
            return len(self._records)

    # --- internals -------------------------------------------------------------
    def _purge_locked(self, now: float) -> None:
        stale = [
            token
            for token, rec in list(self._records.items())
            if now > rec.created_at + self._max_ttl
            or (rec.committed and now > rec.committed_at + self._max_ttl)
        ]
        for token in stale:
            del self._records[token]

    def _evaluate_locked(
        self,
        *,
        content_type: str,
        fingerprint: str,
        sequence: int | None,
        now: float,
    ) -> tuple[SuppressionDecision, str | None]:
        wait_token: str | None = None
        for token, rec in self._records.items():
            if rec.content_type != content_type:
                continue
            if rec.committed:
                decision = self._match_record_locked(rec, fingerprint, sequence, now)
                if decision is SuppressionDecision.SUPPRESS:
                    return (SuppressionDecision.SUPPRESS, token)
                continue
            # Pending record: only wait if the provisional fingerprint matches.
            if rec.fingerprint == fingerprint and wait_token is None:
                wait_token = token
        if wait_token is not None:
            return (SuppressionDecision.WAIT, wait_token)
        return (SuppressionDecision.CAPTURE, None)

    def _match_record_locked(
        self,
        rec: _Record,
        fingerprint: str,
        sequence: int | None,
        now: float,
    ) -> SuppressionDecision:
        # Fingerprint compatibility is always required.  When both sides have
        # sequence numbers, equality additionally confirms ownership; it never
        # substitutes for matching content.
        if sequence is not None and rec.sequence_after is not None:
            if not _u32_equal(sequence, rec.sequence_after):
                # Known mismatch: do not fall back to the fingerprint.
                return SuppressionDecision.CAPTURE
            if rec.fingerprint == fingerprint:
                return SuppressionDecision.SUPPRESS
            return SuppressionDecision.CAPTURE

        # At least one side is missing a sequence number: use canonical fingerprint
        # within the bounded fallback window.
        if rec.committed and now > rec.committed_at + self._fallback_ttl:
            return SuppressionDecision.CAPTURE
        if rec.fingerprint == fingerprint:
            return SuppressionDecision.SUPPRESS
        return SuppressionDecision.CAPTURE

    def _diagnostic(
        self,
        event: str,
        *,
        rec: _Record,
        content_type: str,
        fingerprint: str,
        sequence: int | None,
    ) -> None:
        logger.info(
            "clipboard custody %s: operation=%s token=%s content_type=%s "
            "sequence=%s fingerprint_hash=%s record_age_s=%.3f pending_timeout=%.3f",
            event,
            rec.operation,
            rec.token,
            content_type,
            sequence,
            models.content_hash(fingerprint)[:12],
            self._clock() - rec.created_at,
            self._pending_timeout,
        )


def _u32_equal(a: int, b: int) -> bool:
    """True when two clipboard sequence numbers are equal as unsigned 32-bit counters."""
    return (int(a) & 0xFFFFFFFF) == (int(b) & 0xFFFFFFFF)


class _AttemptResult(NamedTuple):
    """Two independent outcomes of one write attempt -- see
    ``ClipboardWriter._attempt``."""

    custody_commit: bool
    user_visible_success: bool


class ClipboardWriter:
    """Custody-enforcing adapter for every internal clipboard write.

    Callers cannot forget custody: ``begin`` runs before the write, and the
    record is either ``commit``-ed (success) or ``cancel``-ed (failure). The
    actual platform write is delegated to ``via`` (per call) or to the
    configured default (Win32-backed), so both UI-thread Tk writes and
    background-thread Win32 writes share the same suppressor.  The suppressor
    lock is released before the platform call and re-acquired only for the
    short commit/cancel.
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
        """Write ``text`` with custody. ``via`` overrides the write mechanism.

        The suppression fingerprint is the canonical-CRLF form, not ``text``
        verbatim: every writer this coordinates (the default Win32 writer via
        ``_default_set_text``, and every ``via=`` override -- currently only
        the two Tk-based ones in ``ui/clipboard_write.py`` and
        ``ui/shell.py``) ends up placing canonical CRLF on the real clipboard
        (Tk's own CR-insertion-per-LF, or an explicit
        ``canonical_clipboard_text`` call on the raw-Win32 path). The monitor
        fingerprints what it actually reads back off the clipboard, which is
        that same canonical form -- fingerprinting the caller's raw ``text``
        here would silently fail to match for any text whose line-break
        representation changes during the write, and the self-write would be
        wrongly recaptured as a new external clip.
        """
        from . import capture_debug
        from .clipboard_out import canonical_clipboard_text

        write = via or self._set_text
        fingerprint = canonical_clipboard_text(text)
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_TEXT,
            fingerprint=fingerprint,
        )
        sequence_before = self._sequence()
        capture_debug.log(
            "clipboard_write_begin",
            f"operation={operation} token={token} type=text len={len(text)} "
            f"hash={models.content_hash(fingerprint)[:12]} sequence_before={sequence_before}",
        )
        attempt = self._attempt(write, text)
        sequence_after = self._settle(token, attempt.custody_commit, sequence_before=sequence_before)
        capture_debug.log(
            "clipboard_write_settle",
            f"operation={operation} token={token} outcome={'commit' if attempt.custody_commit else 'cancel'} "
            f"user_visible_success={attempt.user_visible_success} "
            f"sequence_before={sequence_before} sequence_after={sequence_after}",
        )
        return attempt.user_visible_success

    def restore_text(self, text: str | None, *, operation: str, via=None) -> bool:
        """Restore ``text`` with custody (snapshot/restore paste flows)."""
        return self._restore_text_attempt(text, operation=operation, via=via).user_visible_success

    def restore_text_commit(self, text: str | None, *, operation: str, via=None) -> tuple[bool, bool]:
        """Restore ``text`` with custody, exposing both outcome signals as
        ``(user_visible_success, custody_commit)``.

        ``custody_commit`` is true whenever the content genuinely reached the
        clipboard, even when ``user_visible_success`` is false (e.g. a
        close-after-set failure) -- callers that need to decide whether a
        failed restore is worth *retrying* must use this instead of the plain
        bool from ``restore_text``: retrying a write that already landed
        would risk a redundant second platform write on top of one that
        already succeeded, which the underlying writer's own contract treats
        as unsound (see ``_write_clipboard_text`` in paste_delivery.py).
        """
        attempt = self._restore_text_attempt(text, operation=operation, via=via)
        return attempt.user_visible_success, attempt.custody_commit

    def _restore_text_attempt(self, text: str | None, *, operation: str, via=None) -> "_AttemptResult":
        from . import capture_debug

        if text is None:
            capture_debug.log(
                "clipboard_restore_skipped",
                f"operation={operation} reason=prior_clipboard_none",
            )
            return _AttemptResult(custody_commit=False, user_visible_success=False)
        write = via or self._restore_text
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_TEXT,
            fingerprint=text,
        )
        sequence_before = self._sequence()
        capture_debug.log(
            "clipboard_restore_begin",
            f"operation={operation} token={token} len={len(text)} "
            f"hash={models.content_hash(text)[:12]} sequence_before={sequence_before}",
        )
        attempt = self._attempt(write, text)
        sequence_after = self._settle(token, attempt.custody_commit, sequence_before=sequence_before)
        capture_debug.log(
            "clipboard_restore_settle",
            f"operation={operation} token={token} outcome={'commit' if attempt.custody_commit else 'cancel'} "
            f"user_visible_success={attempt.user_visible_success} "
            f"sequence_before={sequence_before} sequence_after={sequence_after}",
        )
        return attempt

    def write_image(self, png_bytes: bytes, *, operation: str, via=None) -> bool:
        """Write an image with custody; fingerprint matches the capture path."""
        write = via or self._set_image
        token = self._suppressor.begin(
            operation=operation,
            content_type=models.CONTENT_IMAGE,
            fingerprint=self._image_fingerprint(png_bytes),
        )
        sequence_before = self._sequence()
        attempt = self._attempt(write, png_bytes)
        self._settle(token, attempt.custody_commit, sequence_before=sequence_before)
        return attempt.user_visible_success

    # --- internals ---------------------------------------------------------
    def _attempt(self, write, payload) -> _AttemptResult:
        """Run the platform write and resolve it into two independent
        signals: whether custody should commit (an internal payload may now
        be visible on the clipboard and must be suppressed from recapture)
        and whether the operation succeeded cleanly enough to report to the
        user. A plain bool writer (e.g. simple test lambdas) collapses both
        signals to the same value -- there's no way to distinguish them with
        only one bit of information. A ``ClipboardWriteOutcome`` (the real
        Win32-backed writers) can report them separately -- see
        ``ClipboardWriteOutcome`` in paste_delivery.py for why they diverge.
        """
        from . import capture_debug
        from .paste_delivery import ClipboardWriteOutcome

        try:
            result = write(payload)
        except Exception as exc:  # noqa: BLE001 - a failed write must never capture
            capture_debug.log(
                "clipboard_write_attempt_exception",
                f"type={type(exc).__name__} detail={exc}",
            )
            return _AttemptResult(custody_commit=False, user_visible_success=False)

        if isinstance(result, ClipboardWriteOutcome):
            if not result.user_visible_success:
                capture_debug.log(
                    "clipboard_write_attempt_failed",
                    f"reason=writer_reported_failure error_stage={result.error_stage} "
                    f"content_set={result.content_set} closed={result.closed}",
                )
            return _AttemptResult(
                custody_commit=result.custody_should_commit,
                user_visible_success=result.user_visible_success,
            )

        # Legacy simple bool contract.
        ok = bool(result)
        if not ok:
            capture_debug.log("clipboard_write_attempt_failed", "reason=writer_returned_false")
        return _AttemptResult(custody_commit=ok, user_visible_success=ok)

    def _settle(
        self,
        token: str,
        ok: bool,
        *,
        sequence_before: int | None,
    ) -> int | None:
        if ok:
            sequence_after = self._sequence()
            self._suppressor.commit(
                token,
                sequence_before=sequence_before,
                sequence_after=sequence_after,
            )
            return sequence_after
        else:
            self._suppressor.cancel(token)
            return None

    def _sequence(self) -> int | None:
        try:
            return self._get_sequence()
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _image_fingerprint(png_bytes: bytes) -> str:
        fp = canonical_image_fingerprint(png_bytes)
        if fp is None:
            return models.bytes_hash(png_bytes)
        return fp
