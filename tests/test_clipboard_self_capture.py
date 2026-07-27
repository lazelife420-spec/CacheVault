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
        set_text=sysclip.write,
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
    app.clipboard_clear = lambda: None
    app.clipboard_append = lambda s: h.sysclip.write(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app.after = lambda ms, fn=None, *args: fn(*args) if fn else None
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

    assert h.sysclip.text == "Example Domain - https://example.com\nhttps://google.com"
    assert_no_history_entry(h)


def test_bulk_combined_copy(h):
    vault = FakeVault()
    c1 = make_clip(id="c1", content="first")
    c2 = make_clip(id="c2", content="second")
    vault.storage.clips = {"c1": c1, "c2": c2}
    app = make_app(h, vault)
    app._selected_clip_ids = ["c1", "c2"]

    app._bulk_copy()

    assert h.sysclip.text == "first\n\nsecond"
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
