"""Regression coverage for the visible Copy Combined Text command path."""

from __future__ import annotations

from types import SimpleNamespace

import cache_vault.core.clipboard as clipboard_module
from cache_vault.core import capture_debug, models
from cache_vault.core.clipboard import ClipboardMonitor
from cache_vault.core.clipboard_custody import ClipboardWriteSuppressor, ClipboardWriter
from cache_vault.ui import shell as shell_module
from cache_vault.ui.clip_workflows import ClipComposerDialog, compose_text


class NativeTextClipboard:
    """Model the observable Windows difference between Tk and Win32 writes."""

    def __init__(self) -> None:
        self.text: str | None = None
        self.sequence = 0
        self.write_events: list[tuple[str, str | None]] = []
        self.source_app = "python.exe"

    def tk_clear(self) -> None:
        self.text = None
        self.sequence += 1
        self.write_events.append(("tk_clear", None))

    def tk_append(self, text: str) -> None:
        # Tk exports CF_UNICODETEXT using Windows CRLF line endings.
        self.text = text.replace("\r\n", "\n").replace("\n", "\r\n")
        self.sequence += 1
        self.write_events.append(("tk_append", self.text))

    def win32_write(self, text: str) -> bool:
        self.text = text
        self.sequence += 1
        self.write_events.append(("win32", text))
        return True

    def external_write(self, text: str) -> None:
        self.text = text
        self.sequence += 1
        self.write_events.append(("external", text))


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class TrackingSuppressor(ClipboardWriteSuppressor):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.lifecycle: list[tuple[str, str]] = []

    def begin(self, **kwargs) -> str:
        token = super().begin(**kwargs)
        self.lifecycle.append(("begin", token))
        return token

    def commit(self, token: str, **kwargs) -> bool:
        committed = super().commit(token, **kwargs)
        if committed:
            self.lifecycle.append(("commit", token))
        return committed

    def cancel(self, token: str) -> bool:
        cancelled = super().cancel(token)
        if cancelled:
            self.lifecycle.append(("cancel", token))
        return cancelled


class Storage:
    def __init__(self, clips) -> None:
        self.clips = {clip.id: clip for clip in clips}

    def get_clip(self, clip_id):
        return self.clips.get(clip_id)


def _clip(clip_id: str, text: str):
    return SimpleNamespace(
        id=clip_id,
        content=text,
        content_type=models.CONTENT_TEXT,
        classification="text",
        safe_id=None,
    )


def test_visible_copy_combined_uses_one_exact_guarded_write_and_is_not_ingested(
    monkeypatch,
):
    diagnostics: list[tuple[str, str]] = []
    monkeypatch.setattr(
        capture_debug,
        "log",
        lambda stage, detail="": diagnostics.append((stage, detail)),
    )
    native = NativeTextClipboard()
    suppressor = TrackingSuppressor()
    captures: list[dict] = []
    writer = ClipboardWriter(
        suppressor,
        set_text=native.win32_write,
        get_sequence=lambda: native.sequence,
    )
    monkeypatch.setattr(clipboard_module, "_read_clipboard_text", lambda: native.text)
    monkeypatch.setattr(clipboard_module, "_read_clipboard_image", lambda: None)
    monkeypatch.setattr(
        clipboard_module,
        "_foreground_source",
        lambda: {"source_app": native.source_app, "source_window": "Cache Vault"},
    )
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=lambda: native.sequence,
    )
    monitor._running = True
    if clipboard_module._HAS_WIN32:
        assert monitor.mode == "event"

    clips = [_clip("c1", "alpha Ω"), _clip("c2", "beta")]
    app = object.__new__(shell_module.CacheVaultApp)
    app.vault = SimpleNamespace(storage=Storage(clips))
    app._selected_clip_ids = ["c1", "c2"]
    app._clipboard_writer = writer
    app._guard_unlocked = lambda: True
    app._show_toast = lambda _message: None
    app.clipboard_clear = native.tk_clear
    app.clipboard_append = native.tk_append

    def invoke_visible_dialog(master, *, parts, on_copy, on_save_clip, on_save_macro):
        del master, on_save_clip, on_save_macro
        dialog = object.__new__(ClipComposerDialog)
        dialog._on_copy = on_copy
        combined = compose_text(parts, "blank_line")
        dialog._body = SimpleNamespace(get=lambda *_args: combined)
        ClipComposerDialog._copy(dialog)

    monkeypatch.setattr(shell_module, "ClipComposerDialog", invoke_visible_dialog)

    app._open_clip_composer()
    expected = "alpha Ω\n\nbeta"
    monitor._emit()

    assert native.text.replace("\r\n", "\n") == expected
    assert captures == []
    assert not any(item.get("source_app") == "python.exe" for item in captures)
    assert native.write_events == [("win32", expected)]
    assert [event for event, _token in suppressor.lifecycle] == ["begin", "commit"]
    assert suppressor.lifecycle[0][1] == suppressor.lifecycle[1][1]
    assert len(suppressor) == 0
    assert [stage for stage, _detail in diagnostics] == [
        "clipboard_write_begin",
        "clipboard_write_settle",
        "clipboard_observed",
        "clipboard_custody_decision",
    ]
    assert f"token={suppressor.lifecycle[0][1]}" in diagnostics[0][1]
    assert "operation=copy_generated_text" in diagnostics[0][1]
    assert "outcome=commit" in diagnostics[1][1]
    assert "decision=suppress" in diagnostics[3][1]

    native.source_app = "notepad.exe"
    native.external_write(expected)
    monitor._emit()
    assert captures == [
        {
            "text": expected,
            "clipboard_sequence": native.sequence,
            "source_app": "notepad.exe",
            "source_window": "Cache Vault",
        }
    ]


def test_generated_combined_text_preserves_crlf_unicode_and_gui_separator(monkeypatch):
    native = NativeTextClipboard()
    suppressor = TrackingSuppressor()
    captures: list[dict] = []
    writer = ClipboardWriter(
        suppressor,
        set_text=native.win32_write,
        get_sequence=lambda: native.sequence,
    )
    monkeypatch.setattr(clipboard_module, "_read_clipboard_text", lambda: native.text)
    monkeypatch.setattr(clipboard_module, "_read_clipboard_image", lambda: None)
    monkeypatch.setattr(
        clipboard_module,
        "_foreground_source",
        lambda: {"source_app": native.source_app, "source_window": "Cache Vault"},
    )
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=lambda: native.sequence,
    )
    monitor._running = True
    app = object.__new__(shell_module.CacheVaultApp)
    app._clipboard_writer = writer
    app._show_toast = lambda _message: None

    payload = compose_text(["left\r\nline", "右\nline"], "blank_line")
    app._copy_generated_text(payload, "Copied combined clip.")
    monitor._emit()

    assert payload == "left\r\nline\n\n右\nline"
    assert native.text == payload
    assert captures == []
    assert native.write_events == [("win32", payload)]
    assert [event for event, _token in suppressor.lifecycle] == ["begin", "commit"]


def test_generated_combined_text_survives_delayed_polling_fallback(monkeypatch):
    clock = FakeClock()
    native = NativeTextClipboard()
    suppressor = TrackingSuppressor(clock=clock)
    captures: list[dict] = []
    writer = ClipboardWriter(
        suppressor,
        set_text=native.win32_write,
        get_sequence=lambda: None,
    )
    monkeypatch.setattr(clipboard_module, "_read_clipboard_text", lambda: native.text)
    monkeypatch.setattr(clipboard_module, "_read_clipboard_image", lambda: None)
    monkeypatch.setattr(
        clipboard_module,
        "_foreground_source",
        lambda: {"source_app": native.source_app, "source_window": "Cache Vault"},
    )
    monitor = ClipboardMonitor(
        captures.append,
        suppressor=suppressor,
        get_sequence=lambda: None,
    )
    monitor._running = True
    suppressor.set_monitor_cadence(mode="poll", cadence_s=0.8)
    app = object.__new__(shell_module.CacheVaultApp)
    app._clipboard_writer = writer
    app._show_toast = lambda _message: None

    payload = compose_text(["poll alpha", "poll beta"], "blank_line")
    app._copy_generated_text(payload, "Copied combined clip.")
    clock.advance(0.8)
    monitor._emit()

    assert native.text == "poll alpha\n\npoll beta"
    assert captures == []
    assert len(suppressor) == 0


def test_visible_copy_combined_ignores_empty_selected_text_without_writing(monkeypatch):
    clips = [_clip("c1", "   "), _clip("c2", "\r\n")]
    app = object.__new__(shell_module.CacheVaultApp)
    app.vault = SimpleNamespace(storage=Storage(clips))
    app._selected_clip_ids = ["c1", "c2"]
    app._guard_unlocked = lambda: True
    writes: list[str] = []

    def invoke_empty_dialog(master, *, parts, on_copy, on_save_clip, on_save_macro):
        del master, on_copy, on_save_clip, on_save_macro
        dialog = object.__new__(ClipComposerDialog)
        dialog._on_copy = writes.append
        combined = compose_text(parts, "blank_line")
        dialog._body = SimpleNamespace(get=lambda *_args: combined)
        ClipComposerDialog._copy(dialog)

    monkeypatch.setattr(shell_module, "ClipComposerDialog", invoke_empty_dialog)

    app._open_clip_composer()

    assert writes == []
