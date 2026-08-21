"""Slice A integration: internal clipboard writes must be delivered correctly
AND must never create a new capture-history entry.

Every test drives the real production call path with the real custody wiring
(one suppressor + one writer + monitor sharing it) against a fake system
clipboard that emulates Win32 content + sequence numbers. The foreground
source is deliberately reported as a foreign ``python.exe`` process to prove
custody never relies on executable names.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import cache_vault.core.clipboard as clipmod
from cache_vault.core import copy_clean, models
from cache_vault.core.clipboard import ClipboardMonitor
from cache_vault.core.clipboard_custody import (
    DEFAULT_FALLBACK_TTL_S,
    ClipboardWriteSuppressor,
    ClipboardWriter,
)
from cache_vault.core import paste_delivery
from cache_vault.core.paste_delivery import PasteResult
from cache_vault.ui import shell as shell_mod
from cache_vault.ui.clipboard_write import write_text_via_app
from cache_vault.ui.quick_paste import ACTION_COPY_ONLY


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class FakeSystemClipboard:
    """Win32 clipboard stand-in: content plus a monotonically increasing
    sequence number that bumps on every write."""

    def __init__(self) -> None:
        self.text: str | None = None
        self.seq = 0

    def write(self, text: str) -> bool:
        self.text = text
        self.seq += 1
        return True

    def write_canonical(self, text: str) -> bool:
        # Stands in for the default (set_text=) writer role specifically:
        # set_clipboard_text / _set_clipboard_text_outcome canonicalizes to
        # CRLF before the platform write (see ClipboardWriter.write_text's
        # fingerprint docstring), unlike restore_text=write above, which must
        # stay byte-exact -- real production is asymmetric here, so this fake
        # keeps write() (restore role) and write_canonical() (set role)
        # separate rather than making the one write() function context-aware.
        from cache_vault.core.clipboard_out import canonical_clipboard_text
        return self.write(canonical_clipboard_text(text))


@pytest.fixture
def h(monkeypatch):
    sysclip = FakeSystemClipboard()
    monkeypatch.setattr(clipmod, "_read_clipboard_text", lambda: sysclip.text)
    monkeypatch.setattr(clipmod, "_read_clipboard_image", lambda: None)
    monkeypatch.setattr(
        clipmod,
        "_foreground_source",
        lambda: {"source_app": "python.exe", "source_window": "external-shell"},
    )
    suppressor = ClipboardWriteSuppressor()
    captures: list[dict] = []
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=lambda: sysclip.seq,
    )
    monitor._running = True  # drive _emit directly; no listener thread needed
    writer = ClipboardWriter(
        suppressor,
        set_text=sysclip.write_canonical,
        restore_text=sysclip.write,
        get_sequence=lambda: sysclip.seq,
    )
    return SimpleNamespace(
        sysclip=sysclip,
        suppressor=suppressor,
        monitor=monitor,
        writer=writer,
        captures=captures,
    )


def emit(h) -> None:
    """Simulate one WM_CLIPBOARDUPDATE reaching the monitor."""
    h.monitor._emit()


def assert_no_history_entry(h) -> None:
    emit(h)
    assert h.captures == []


# --- stub vault / app ---------------------------------------------------------

class FakeEvents:
    def __init__(self) -> None:
        self.records: list[tuple] = []

    def record(self, event_type, clip_id, payload) -> None:
        self.records.append((event_type, clip_id, payload))


class FakeStorage:
    def __init__(self) -> None:
        self.clips: dict = {}

    def get_clip(self, clip_id):
        return self.clips.get(clip_id)

    def touch_clip(self, clip_id) -> None:
        pass


class FakeVault:
    def __init__(self, settings=None) -> None:
        self.storage = FakeStorage()
        self.events = FakeEvents()
        self.settings = settings or SimpleNamespace(
            restore_clipboard_after_paste=False,
            auto_paste=False,
        )
        self.pasted: list[dict] = []

    def copied_again(self, clip_id):
        clip = self.storage.get_clip(clip_id)
        return clip.content if clip else None

    def log_item_pasted(self, clip_id, **kwargs) -> None:
        self.pasted.append({"clip_id": clip_id, **kwargs})


def make_clip(**kw):
    defaults = dict(
        id="c1",
        content="hello world",
        classification="text",
        content_type=models.CONTENT_TEXT,
        title=None,
        source_app="chrome.exe",
        source_url=None,
        created_at="2026-07-27T10:00:00",
        date_used="2026-07-27T10:05:00",
        use_count=3,
        is_sensitive=False,
        is_pinned=False,
        content_hash="0123456789abcdef0123456789abcdef",
        preview="hello world",
        safe_id=None,
        safe_name=None,
        capture_mode="auto",
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def make_app(h, vault):
    app = object.__new__(shell_mod.CacheVaultApp)
    app.vault = vault
    app._selected_clip_ids = []
    app._toasts: list[str] = []
    app._clipboard_writer = h.writer
    app._guard_unlocked = lambda: True
    app._locked = lambda: False
    app._block_if_matching_active = lambda _name: False
    # Adapted during the clipboard-custody integration (Gate 5F-B):
    # _schedule_clipboard_restore's deferred _restore() calls self._alive(),
    # which reads self._shutting_down (unguarded -- unlike the rest of
    # destroy()-style chains in this codebase, this one attribute access
    # isn't try/except-wrapped) and falls back to self.winfo_exists() (a real
    # Tk method this bare object.__new__ stub doesn't have). Stub _alive
    # directly rather than winfo_exists/_shutting_down individually, matching
    # the same "override the method, not the internals" pattern already used
    # for _guard_unlocked/_locked/_block_if_matching_active above.
    app._alive = lambda: True
    app.clipboard_clear = lambda: None
    # Real Tk's clipboard_append renders the selection itself and inserts a
    # CR before every LF, unconditionally -- _tk_set_clipboard_text feeds it
    # LF-normalized text expecting exactly that, producing canonical CRLF
    # (see clipboard_out.write_via_tk / _tk_set_clipboard_text). This stub
    # must simulate that CR-insertion, not just store the string verbatim,
    # or the fake clipboard ends up LF-only while write_text's custody
    # fingerprint (always canonical CRLF) no longer matches it.
    app.clipboard_append = lambda s: h.sysclip.write(s.replace("\r\n", "\n").replace("\n", "\r\n"))
    app._show_toast = lambda msg: app._toasts.append(msg)
    app.after = lambda ms, fn=None, *args: fn(*args) if fn else None
    # Adapted onto a baseline that added a Quick Paste status-feedback path
    # (_notify_quick_paste_or_toast) after this branch's own divergence point.
    # Built via object.__new__, bypassing __init__, so _quick_paste is never
    # set as a real instance attribute -- getattr(self, "_quick_paste", None)
    # would otherwise fall through to Tk's own __getattr__ proxy (which also
    # has no real instance state here) and recurse indefinitely.
    app._quick_paste = None
    return app


class FakeWidget:
    """Stands in for a dialog widget; routes to the app's custody writer."""

    def __init__(self, h) -> None:
        self._h = h
        self._root = SimpleNamespace(_clipboard_writer=h.writer)

    def winfo_toplevel(self):
        return self._root

    def clipboard_clear(self) -> None:
        pass

    def clipboard_append(self, s: str) -> None:
        self._h.sysclip.write(s)


# --- inventoried writer paths -------------------------------------------------

def test_single_clip_copy(h):
    vault = FakeVault()
    vault.storage.clips["c1"] = make_clip(content="alpha clip")
    app = make_app(h, vault)

    app._copy_again("c1")

    assert h.sysclip.text == "alpha clip"
    assert_no_history_entry(h)
    assert len(h.suppressor) == 0


def test_copy_metadata(h):
    vault = FakeVault()
    clip = make_clip()
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)

    app._copy_metadata("c1")

    expected = (
        f"type={clip.classification} source={clip.source_app} "
        f"created={clip.created_at} last_used={clip.date_used} "
        f"use_count={clip.use_count} sensitive={clip.is_sensitive} "
        f"hash={clip.content_hash[:12]}"
    )
    assert h.sysclip.text == expected
    assert_no_history_entry(h)


def test_copy_plain_text(h):
    vault = FakeVault()
    clip = make_clip(content="plain body text")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)

    app._copy_clean("c1", copy_clean.COPY_PLAIN_TEXT)

    expected = copy_clean.format_clip(clip, copy_clean.COPY_PLAIN_TEXT)
    assert expected
    assert h.sysclip.text == expected
    assert_no_history_entry(h)


def test_copy_markdown_link(h):
    vault = FakeVault()
    clip = make_clip(
        classification=models.CLASS_LINK,
        content="https://example.com/page",
        title="Example",
    )
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)

    app._copy_clean("c1", copy_clean.COPY_MARKDOWN)

    expected = copy_clean.format_clip(clip, copy_clean.COPY_MARKDOWN)
    assert expected and "[" in expected and "](https://example.com/page)" in expected
    assert h.sysclip.text == expected
    assert_no_history_entry(h)


def test_copy_path(h):
    vault = FakeVault()
    vault.storage.clips["c1"] = make_clip(
        classification=models.CLASS_PATH,
        content="C:\\Users\\KickA\\Documents\\file.txt",
    )
    app = make_app(h, vault)

    app._copy_path("c1")

    assert h.sysclip.text == "C:\\Users\\KickA\\Documents\\file.txt"
    assert_no_history_entry(h)


def test_copy_combined_text(h):
    vault = FakeVault()
    c1 = make_clip(id="c1", classification=models.CLASS_LINK,
                   content="https://example.com", title="Example Domain")
    c2 = make_clip(id="c2", classification=models.CLASS_LINK,
                   content="https://google.com")
    vault.storage.clips = {"c1": c1, "c2": c2}
    app = make_app(h, vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy_format("plain")

    # Tk's clipboard_append inserts a CR before every LF; _tk_set_clipboard_text
    # feeds it LF-normalized text expecting exactly that, so the real clipboard
    # ends up with canonical CRLF, not the LF-only source string.
    assert h.sysclip.text == "Example Domain - https://example.com\r\nhttps://google.com"
    assert_no_history_entry(h)


def test_bulk_combined_copy(h):
    vault = FakeVault()
    c1 = make_clip(id="c1", content="first")
    c2 = make_clip(id="c2", content="second")
    vault.storage.clips = {"c1": c1, "c2": c2}
    app = make_app(h, vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy()

    # Tk's clipboard_append inserts a CR before every LF; _tk_set_clipboard_text
    # feeds it LF-normalized text expecting exactly that, so the real clipboard
    # ends up with canonical CRLF, not the LF-only source string.
    assert h.sysclip.text == "first\r\n\r\nsecond"
    assert_no_history_entry(h)


def test_receipt_and_proof_hash_copy(h):
    from cache_vault.ui.dialogs import EventLogDialog

    dlg = object.__new__(EventLogDialog)
    dlg._selected = SimpleNamespace(proof_hash="deadbeef" * 8)
    dlg._format_receipt_copy_fn = lambda row: "RECEIPT SUMMARY TEXT"
    root = SimpleNamespace(_clipboard_writer=h.writer)
    dlg.winfo_toplevel = lambda: root
    dlg.clipboard_clear = lambda: None
    dlg.clipboard_append = lambda s: h.sysclip.write(s)

    dlg._copy_receipt()
    assert h.sysclip.text == "RECEIPT SUMMARY TEXT"
    assert_no_history_entry(h)

    dlg._copy_hash()
    assert h.sysclip.text == "deadbeef" * 8
    assert_no_history_entry(h)


def test_mobile_and_pairing_address_copy(h):
    from cache_vault.ui import mobile_dialogs

    widget = FakeWidget(h)

    mobile_dialogs._copy_to_clipboard(widget, '{"pairing":"payload"}')
    assert h.sysclip.text == '{"pairing":"payload"}'
    assert_no_history_entry(h)

    write_text_via_app(widget, "192.168.1.10:8742", operation="copy_pairing_address")
    assert h.sysclip.text == "192.168.1.10:8742"
    assert_no_history_entry(h)


def test_founder_license_copy(h, monkeypatch):
    from cache_vault.ui import founder as founder_mod

    monkeypatch.setattr(founder_mod, "_purchase_url", lambda: "https://buy.example/founder")
    monkeypatch.setattr(
        founder_mod.messagebox, "showinfo", lambda *a, **k: None,
    )

    dlg = object.__new__(founder_mod.FounderDialog)
    root = SimpleNamespace(_clipboard_writer=h.writer)
    dlg.winfo_toplevel = lambda: root
    dlg.clipboard_clear = lambda: None
    dlg.clipboard_append = lambda s: h.sysclip.write(s)

    dlg._copy_purchase_link()

    assert h.sysclip.text == "https://buy.example/founder"
    assert_no_history_entry(h)


def test_quick_paste_delivery(h, monkeypatch):
    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    vault = FakeVault()
    clip = make_clip(content="qp body")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._paste_target = None

    app._do_paste(clip, ACTION_COPY_ONLY)

    assert h.sysclip.text == "qp body"
    assert_no_history_entry(h)
    assert any(r[0] == "quick_paste_copy_only" for r in vault.events.records)


def test_quick_paste_restoration(h, monkeypatch):
    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._paste_target = 4242

    h.sysclip.write("PRIOR CLIPBOARD")  # external content before quick paste
    app._do_paste(clip, "primary")

    # delivery wrote the clip, then custody-wrapped restore put PRIOR back
    assert h.sysclip.text == "PRIOR CLIPBOARD"
    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is True
    # the restore event (latest sequence) is suppressed
    emit(h)
    assert h.captures == []
    remaining_ops = [r["operation"] for r in h.suppressor.snapshot()]
    assert "quick_paste_restore" not in remaining_ops


def test_quick_paste_restoration_reports_failure_when_restore_write_fails(h, monkeypatch):
    """Regression: clipboard_restored must reflect the ACTUAL restore write
    outcome, not be assumed from (setting enabled and delivery succeeded).

    The real win32 restore write can silently fail (e.g. OpenClipboard
    contention with the paste target) while the delivered content stays on
    the clipboard -- and the app used to still report clipboard_restored=True
    because it never checked the write's own return value. (This is a
    code-level diagnosis; no native/live OS-level reproduction is claimed
    here. See test_clipboard_open_retry.py for the isolated retry-path tests
    and test_quick_paste_restoration_recovers_after_transient_open_failure
    below for the integrated retry-through-restoration path.) This drives
    the exact same _do_paste path with a writer whose restore call fails,
    and asserts the app tells the truth about it.
    """
    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))

    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )
    failing_writer = ClipboardWriter(
        h.suppressor,
        set_text=h.sysclip.write,
        restore_text=lambda _text: False,  # simulates a real OpenClipboard race
        get_sequence=lambda: h.sysclip.seq,
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._clipboard_writer = failing_writer
    app._paste_target = 4242

    h.sysclip.write("PRIOR CLIPBOARD")
    app._do_paste(clip, "primary")

    # the restore write failed, so the delivered content is still on the clipboard
    assert h.sysclip.text == "pasted content"
    # and the app must not claim restoration succeeded when it didn't
    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is False
    # the failed restore token must not survive -- it was cancelled, not left
    # open (the delivery write's own token is a separate, legitimately
    # committed record and is unaffected).
    ops = [r["operation"] for r in h.suppressor.snapshot()]
    assert "quick_paste_restore" not in ops
    assert "quick_paste_deliver" in ops
    # positive diagnostic proof of the failure path (paired with the
    # disabled-path test below, which proves the *absence* of these same
    # two log entries -- together they show the two cases are genuinely
    # distinguishable, not just coincidentally absent from the ops snapshot).
    restore_stages = [(s, d) for s, d in logged if s in ("clipboard_restore_begin", "clipboard_restore_settle")]
    assert any(s == "clipboard_restore_begin" for s, _ in restore_stages)
    assert any(s == "clipboard_restore_settle" and "outcome=cancel" in d for s, d in restore_stages)


def test_quick_paste_delivery_success_is_not_reported_as_restoration_success(h, monkeypatch):
    """A successful delivery must never be conflated with a successful
    restoration -- they are two independent custody-guarded writes."""
    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )
    failing_writer = ClipboardWriter(
        h.suppressor,
        set_text=h.sysclip.write,
        restore_text=lambda _text: False,
        get_sequence=lambda: h.sysclip.seq,
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._clipboard_writer = failing_writer
    app._paste_target = 4242

    app._do_paste(clip, "primary")

    # delivery itself succeeded (Toast/log would report success for it)...
    assert vault.pasted and vault.pasted[0]["success"] is True
    # ...but that must not leak into the independent restoration outcome
    assert vault.pasted[0]["clipboard_restored"] is False


def test_quick_paste_restoration_disabled_is_distinguishable_from_failed(h, monkeypatch):
    """restore_clipboard_after_paste=False and a genuine restore failure both
    surface clipboard_restored=False, and BOTH end up absent from the custody
    ops snapshot (a cancelled token is popped just like a never-opened one --
    see ClipboardWriteSuppressor.cancel). So the ops snapshot alone does NOT
    prove they're distinguishable; this asserts on the diagnostic trail
    instead, where the real difference lives: disabled means restore_text()
    is never called at all, so no clipboard_restore_begin/settle diagnostic
    ever fires. Compare against
    test_quick_paste_restoration_reports_failure_when_restore_write_fails,
    which proves the failure path DOES emit both.
    """
    import cache_vault.core.capture_debug as capture_debug_mod

    logged: list[tuple[str, str]] = []
    monkeypatch.setattr(capture_debug_mod, "log", lambda stage, detail: logged.append((stage, detail)))

    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=False, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._paste_target = 4242

    app._do_paste(clip, "primary")

    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is False
    ops = [r["operation"] for r in h.suppressor.snapshot()]
    assert "quick_paste_restore" not in ops
    restore_stages = [(s, d) for s, d in logged if s in ("clipboard_restore_begin", "clipboard_restore_settle")]
    assert restore_stages == [], (
        f"disabled must never emit a restore begin/settle diagnostic, got {restore_stages}"
    )


def test_quick_paste_restoration_recovers_after_transient_open_failure(h, monkeypatch):
    """Integrated test: drives the REAL restore path end-to-end --
    _do_paste -> ClipboardWriter.restore_text -> the default writer ->
    paste_delivery.restore_clipboard_text -> _open_clipboard_with_retry --
    against a fake win32clipboard whose OpenClipboard fails transiently
    before succeeding. Every other test in this file that exercises restore
    failure uses a lambda stand-in (restore_text=lambda _text: False); this
    one does not -- it proves the retry logic in paste_delivery.py actually
    composes correctly with the app + custody layers, not just in isolation
    (test_clipboard_open_retry.py) or with the app layer alone (the
    lambda-based tests above).
    """
    import sys

    class _TransientlyFlakyClipboard:
        """OpenClipboard fails `fail_times` times (transient contention),
        then succeeds; Empty/Set/Close behave normally throughout."""

        def __init__(self, fail_times: int) -> None:
            self.fail_times = fail_times
            self.opens = 0
            self.closed = 0
            self.set_calls: list[tuple[int, str]] = []

        def OpenClipboard(self) -> None:
            self.opens += 1
            if self.opens <= self.fail_times:
                raise OSError("Cannot open Clipboard (transient)")

        def EmptyClipboard(self) -> None:
            pass

        def SetClipboardData(self, fmt, text) -> None:
            self.set_calls.append((fmt, text))

        def CloseClipboard(self) -> None:
            self.closed += 1

    fake = _TransientlyFlakyClipboard(fail_times=2)
    fake_module = SimpleNamespace(
        OpenClipboard=fake.OpenClipboard,
        EmptyClipboard=fake.EmptyClipboard,
        SetClipboardData=fake.SetClipboardData,
        CloseClipboard=fake.CloseClipboard,
    )
    monkeypatch.setitem(sys.modules, "win32clipboard", fake_module)
    monkeypatch.setattr(paste_delivery, "win32con", SimpleNamespace(CF_UNICODETEXT=13), raising=False)
    monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True, raising=False)
    monkeypatch.setattr(paste_delivery.time, "sleep", lambda s: None)

    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )

    recovering_writer = ClipboardWriter(
        h.suppressor,
        set_text=h.sysclip.write,
        restore_text=None,  # default -> real paste_delivery.restore_clipboard_text
        get_sequence=lambda: h.sysclip.seq,
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._clipboard_writer = recovering_writer
    app._paste_target = 4242

    h.sysclip.write("PRIOR CLIPBOARD")
    app._do_paste(clip, "primary")

    # OpenClipboard was genuinely retried (2 failures + 1 success) -- this
    # is not a first-try success and not a lambda stand-in.
    assert fake.opens == 3
    # the retry ultimately succeeded, so the real prior content landed via
    # the actual SetClipboardData call.
    assert fake.set_calls == [(13, "PRIOR CLIPBOARD")]
    assert fake.closed == 1
    # the app reports the true (recovered) outcome
    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is True
    # committed, not cancelled -- the retry's eventual success is reflected
    # in custody, not just in the boolean return value.
    records = h.suppressor.snapshot()
    restore_recs = [r for r in records if r["operation"] == "quick_paste_restore"]
    assert restore_recs and restore_recs[0]["committed"] is True


def test_quick_paste_restoration_close_failure_via_real_production_path(h, monkeypatch):
    """Same proof as test_quick_paste_restoration_close_failure_commits_custody_but_reports_failure
    below, but constructs ClipboardWriter exactly as production does --
    restore_text=None (the real default _default_restore_text), not an
    injected ClipboardWriteOutcome lambda. This exercises the actual chain
    used by CacheVaultApp: ClipboardWriter(suppressor) [shell.py's real
    construction has no restore_text override either] -> _default_restore_text
    -> paste_delivery._restore_clipboard_text_outcome -> _write_clipboard_text
    -> a real (faked-at-the-win32-boundary) CloseClipboard failure, proving
    the structured outcome is not collapsed to bool anywhere on this path.
    """
    import sys

    class _CloseFailsClipboard:
        def __init__(self) -> None:
            self.opens = 0
            self.closed = 0
            self.set_calls: list[tuple[int, str]] = []

        def OpenClipboard(self) -> None:
            self.opens += 1

        def EmptyClipboard(self) -> None:
            pass

        def SetClipboardData(self, fmt, text) -> None:
            self.set_calls.append((fmt, text))

        def CloseClipboard(self) -> None:
            self.closed += 1
            raise OSError("CloseClipboard failed")

    fake = _CloseFailsClipboard()
    fake_module = SimpleNamespace(
        OpenClipboard=fake.OpenClipboard,
        EmptyClipboard=fake.EmptyClipboard,
        SetClipboardData=fake.SetClipboardData,
        CloseClipboard=fake.CloseClipboard,
    )
    monkeypatch.setitem(sys.modules, "win32clipboard", fake_module)
    monkeypatch.setattr(paste_delivery, "win32con", SimpleNamespace(CF_UNICODETEXT=13), raising=False)
    monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True, raising=False)

    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )

    # restore_text=None -- the real default (_default_restore_text), exactly
    # what shell.py's actual `ClipboardWriter(self._clipboard_suppressor)`
    # construction produces. No lambda, no pre-built outcome.
    real_default_writer = ClipboardWriter(
        h.suppressor,
        set_text=h.sysclip.write,
        get_sequence=lambda: h.sysclip.seq,
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._clipboard_writer = real_default_writer
    app._paste_target = 4242

    h.sysclip.write("PRIOR CLIPBOARD")  # only tracked for the delivery leg
    app._do_paste(clip, "primary")

    # the real SetClipboardData call happened (content genuinely set)...
    assert fake.set_calls == [(13, "PRIOR CLIPBOARD")]
    assert fake.closed == 1
    # ...but the UI must not claim clean restoration success
    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is False
    # ...while custody committed -- proving the structured outcome, not a
    # collapsed bool, reached ClipboardWriter._attempt() on the real path.
    records = h.suppressor.snapshot()
    restore_recs = [r for r in records if r["operation"] == "quick_paste_restore"]
    assert restore_recs and restore_recs[0]["committed"] is True


def test_quick_paste_restoration_close_failure_commits_custody_but_reports_failure(h, monkeypatch):
    """Content-set + close-failure: custody must commit (the internal payload
    may be visible on the clipboard and must not be recaptured as new
    history), but the UI must report clipboard_restored=False (the
    transaction did not close cleanly). A single bool cannot represent both
    -- this proves paste_delivery.ClipboardWriteOutcome's dual signal
    actually reaches both custody and the UI correctly, and that no internal
    clip ingestion happens despite the close failure.
    """
    monkeypatch.setattr(shell_mod, "Toast", lambda *a, **k: None)
    monkeypatch.setattr(shell_mod, "hwnd_belongs_to_widget", lambda hwnd, w: False)
    monkeypatch.setattr(shell_mod, "snapshot_clipboard_text", lambda: h.sysclip.text)
    monkeypatch.setattr(
        shell_mod, "deliver_ctrl_v",
        lambda hwnd: PasteResult(True, "ok", "Notepad"),
    )

    close_failed_outcome = paste_delivery.ClipboardWriteOutcome(
        opened=True, content_set=True, closed=False, error_stage="CloseClipboard",
    )

    def _restore_with_close_failure(text):
        h.sysclip.write(text)  # the content really did land on the (simulated) clipboard
        return close_failed_outcome

    writer = ClipboardWriter(
        h.suppressor,
        set_text=h.sysclip.write,
        restore_text=_restore_with_close_failure,
        get_sequence=lambda: h.sysclip.seq,
    )
    settings = SimpleNamespace(restore_clipboard_after_paste=True, auto_paste=True)
    vault = FakeVault(settings)
    clip = make_clip(content="pasted content")
    vault.storage.clips["c1"] = clip
    app = make_app(h, vault)
    app._clipboard_writer = writer
    app._paste_target = 4242

    h.sysclip.write("PRIOR CLIPBOARD")
    app._do_paste(clip, "primary")

    # the content genuinely landed on the (simulated) clipboard...
    assert h.sysclip.text == "PRIOR CLIPBOARD"
    # ...but the UI must not claim clean restoration success
    assert vault.pasted and vault.pasted[0]["clipboard_restored"] is False
    # ...while custody committed (not cancelled) -- the payload must be
    # suppressed from recapture even though the UI reports failure.
    records = h.suppressor.snapshot()
    restore_recs = [r for r in records if r["operation"] == "quick_paste_restore"]
    assert restore_recs and restore_recs[0]["committed"] is True

    # and no internal clip ingestion happens for this write -- the monitor
    # must suppress it despite clipboard_restored=False.
    emit(h)
    assert h.captures == []


def test_macro_clipboard_output(h, tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    from cache_vault.core.macro_execute import MacroExecutor
    from cache_vault.core.settings import Settings
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.vault import Vault
    from cache_vault.core.vault_macros import (
        Macro,
        MacroSafeRegistry,
        MacroStore,
        OUTPUT_CLIPBOARD_PASTE,
        TRIGGER_MENU_ONLY,
    )

    settings = Settings()
    settings.vault_macros_enabled = True
    settings.vault_macros_setup_completed = True
    store = MacroStore(tmp_path / "CacheVault" / "macros.json")
    registry = MacroSafeRegistry(settings)
    vault = Vault(storage=VaultStorage(":memory:"), settings=settings)
    try:
        executor = MacroExecutor(
            settings,
            store,
            registry,
            vault.events,
            confirm_sensitive=lambda _label: True,
            clipboard_writer=h.writer,
        )
        macro = Macro(
            id="m1",
            name="Greeting",
            body="expanded macro body",
            enabled=True,
            trigger_type=TRIGGER_MENU_ONLY,
            output_mode=OUTPUT_CLIPBOARD_PASTE,
        )

        result = executor.execute(macro, trigger_type=TRIGGER_MENU_ONLY, target_hwnd=None)

        assert result.ok
        assert h.sysclip.text == "expanded macro body"
        assert_no_history_entry(h)
    finally:
        vault.close()


# --- custody behavior through the monitor --------------------------------------

def test_failed_write_cancellation(h):
    ok = h.writer.write_text("never landed", operation="copy_clip", via=lambda t: False)
    assert ok is False

    h.sysclip.write("never landed")  # some other writer puts identical text up
    emit(h)
    assert [p["text"] for p in h.captures] == ["never landed"]


def test_sequence_mismatch_is_captured(h):
    assert h.writer.write_text("same text", operation="copy_clip") is True  # seq 1 record
    h.sysclip.write("same text")  # external identical write -> seq 2

    emit(h)
    assert [p["text"] for p in h.captures] == ["same text"]
    # our record was not consumed by the foreign event
    assert len(h.suppressor) == 1


def test_missing_sequence_fallback(h):
    clock = FakeClock()
    suppressor = ClipboardWriteSuppressor(clock=clock)
    captures: list[dict] = []
    monitor = ClipboardMonitor(
        captures.append, suppressor=suppressor, get_sequence=lambda: None,
    )
    monitor._running = True
    writer = ClipboardWriter(
        suppressor, set_text=h.sysclip.write, get_sequence=lambda: None,
    )

    assert writer.write_text("fallback clip", operation="copy_clip") is True
    monitor._emit()
    assert captures == []  # fingerprint match inside the fallback TTL

    clock.advance(DEFAULT_FALLBACK_TTL_S + 0.01)
    h.sysclip.write("genuine new clip")
    monitor._emit()
    assert [p["text"] for p in captures] == ["genuine new clip"]


def test_rapid_identical_writes(h):
    assert h.writer.write_text("dup", operation="copy_clip") is True
    emit(h)
    assert h.writer.write_text("dup", operation="copy_clip") is True
    emit(h)
    assert h.captures == []
    assert len(h.suppressor) == 0


def test_later_genuine_identical_user_copy(h):
    assert h.writer.write_text("recopy me", operation="copy_clip") is True
    emit(h)
    assert h.captures == []

    h.sysclip.write("recopy me")  # user genuinely copies the same text later
    emit(h)
    assert [p["text"] for p in h.captures] == ["recopy me"]


def test_unrelated_python_application_capture(h):
    h.sysclip.write("copied in another python app")  # no custody record at all
    emit(h)
    assert len(h.captures) == 1
    payload = h.captures[0]
    assert payload["text"] == "copied in another python app"
    # foreground source is python.exe and capture still happened:
    # custody never excludes by executable name
    assert payload["source_app"] == "python.exe"


def test_concurrent_writer_monitor_access(h):
    import threading

    errors: list[BaseException] = []
    lock = threading.Lock()

    def writer_thread(n: int) -> None:
        for i in range(40):
            try:
                h.writer.write_text(f"t{n}-{i}", operation="stress")
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

    def monitor_thread() -> None:
        for _ in range(320):
            try:
                emit(h)
            except BaseException as exc:  # noqa: BLE001
                with lock:
                    errors.append(exc)

    threads = [threading.Thread(target=writer_thread, args=(n,)) for n in range(4)]
    threads += [threading.Thread(target=monitor_thread) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    for payload in h.captures:
        assert payload["text"].startswith("t")


# --- regression: the pre-Slice-A native symptom ---------------------------------

def test_regression_pre_slice_a_self_capture_race(h):
    """Pre-Slice-A wiring: monitor without a suppressor, note_local_copy
    called only after the write. The clipboard event beats the marker and the
    app recaptures its own write — the native symptom."""
    captures: list[dict] = []
    legacy = ClipboardMonitor(captures.append, get_sequence=lambda: None)
    legacy._running = True

    h.sysclip.write("internal write")
    legacy._emit()  # event processed before note_local_copy (the race)

    assert [p["text"] for p in captures] == ["internal write"]  # symptom reproduced
    legacy.note_local_copy("internal write")  # too late


def test_regression_pre_slice_a_identical_recopy_swallowed(h):
    """Pre-Slice-A wiring: the sticky note_local_copy marker swallows a later
    genuine identical user copy."""
    captures: list[dict] = []
    legacy = ClipboardMonitor(captures.append, get_sequence=lambda: None)
    legacy._running = True

    legacy.note_local_copy("x")
    h.sysclip.write("x")
    legacy._emit()
    assert captures == []  # own write suppressed (legacy intent)

    h.sysclip.write("x")  # later genuine identical copy from another app
    legacy._emit()
    assert captures == []  # symptom: never captured


def test_slice_a_fixes_both_symptoms(h):
    h.writer.write_text("x", operation="copy_clip")
    emit(h)
    assert h.captures == []  # own write suppressed via custody

    h.sysclip.write("x")  # later genuine identical copy
    emit(h)
    assert [p["text"] for p in h.captures] == ["x"]  # captured again
