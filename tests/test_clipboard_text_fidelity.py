"""Text fidelity for everything CacheVault copies back out.

User report: copying several links and pasting them did not reproduce the
original line spacing, and Combine Clips damaged spacing the same way.

Root cause, measured on Windows with a separate reader process rather than
assumed: Tk's ``clipboard_append`` renders the selection itself and inserts a CR
before *every* LF. Captured Windows text already contains CRLF (capture reads raw
CF_UNICODETEXT and storage keeps it byte-verbatim), so copying a multi-line clip
put CR CR LF on the clipboard, which apps render as an extra blank line:

    written 'A\r\nB'  ->  another process read back 'A\r\r\nB'

The win32 writer used by Quick Paste/macros has the opposite problem: it is
byte-faithful, so LF-only text stayed LF-only and Windows edit controls ran the
lines together.

``_as_windows_clipboard`` below models the measured Tk behaviour so these tests
can assert what a pasting application actually receives without touching the
real system clipboard.
"""

from __future__ import annotations

import os
import sys
import types

import pytest

from cache_vault.core import clipboard_out, multi_link, paste_delivery
from cache_vault.ui.clip_workflows import compose_text

# Reproduction cases from the report.
CASE_A = "https://example.com/a\r\nhttps://example.com/b\r\nhttps://example.com/c"
CASE_B = "https://example.com/a\r\n\r\nhttps://example.com/b\r\n\r\nhttps://example.com/c"
CASE_C = "label one\r\nhttps://example.com/a\r\nlabel two\r\nhttps://example.com/b"
CASE_D = "two  spaces\tand a tab\r\n\tindented line  \r\n\r\ntrailing blank above"
ALL_CASES = {"A_consecutive_links": CASE_A, "B_blank_line_separated": CASE_B,
             "C_label_link_pairs": CASE_C, "D_spaces_and_tabs": CASE_D}


class _FakeClipboardWidget:
    """Records what would be handed to Tk's clipboard."""

    def __init__(self) -> None:
        self.clear_calls = 0
        self.appended: list[str] = []

    def clipboard_clear(self) -> None:
        self.clear_calls += 1
        self.appended.clear()

    def clipboard_append(self, text: str) -> None:
        self.appended.append(text)

    @property
    def handed_to_tk(self) -> str:
        return "".join(self.appended)


def _as_windows_clipboard(text: str) -> str:
    """What a Windows app reads back for text handed to Tk's clipboard.

    Tk inserts a CR before every LF, unconditionally -- so an LF becomes CRLF and
    an existing CRLF becomes CR CR LF. Verified against a real Tk on Windows.
    """
    return "".join("\r\n" if ch == "\n" else ch for ch in text)


def _copy_out(text: str) -> str:
    """Copy ``text`` the way the UI does, and return what a paster receives."""
    widget = _FakeClipboardWidget()
    reported = clipboard_out.write_via_tk(widget, text)
    seen = _as_windows_clipboard(widget.handed_to_tk)
    if os.name == "nt":
        # The value handed to note_local_copy must equal what is really on the
        # clipboard, or the monitor re-captures our own copy as a new clip.
        assert reported == seen
    return seen


# --- the canonical form -------------------------------------------------------

def test_normalize_to_lf_only_touches_line_endings():
    assert clipboard_out.normalize_to_lf("a\r\nb\rc\nd") == "a\nb\nc\nd"
    # Everything that is not a line ending survives untouched.
    busy = "two  spaces\tand tab\r\n\tindented  \r\n\r\nend"
    assert clipboard_out.normalize_to_lf(busy) == "two  spaces\tand tab\n\tindented  \n\nend"


def test_canonical_clipboard_text_is_crlf_and_idempotent():
    assert clipboard_out.canonical_clipboard_text("a\nb") == "a\r\nb"
    assert clipboard_out.canonical_clipboard_text("a\r\nb") == "a\r\nb"
    once = clipboard_out.canonical_clipboard_text(CASE_B)
    assert clipboard_out.canonical_clipboard_text(once) == once


def test_write_via_tk_hands_tk_lf_only_text():
    widget = _FakeClipboardWidget()
    clipboard_out.write_via_tk(widget, CASE_A)
    handed = widget.handed_to_tk
    assert "\r" not in handed, "Tk must never be handed a CR; it adds its own"
    assert handed.count("\n") == 2
    assert widget.clear_calls == 1


# --- the reported reproductions ------------------------------------------------

@pytest.mark.parametrize("name", sorted(ALL_CASES))
def test_copy_out_preserves_line_structure(name):
    """The regression: a CRLF clip copied out must not gain blank lines."""
    original = ALL_CASES[name]
    seen = _copy_out(original)
    assert seen == clipboard_out.canonical_clipboard_text(original)
    assert "\r\r" not in seen, "extra CR would show up as an added blank line"
    # Line structure is identical once line endings are compared like for like.
    assert clipboard_out.normalize_to_lf(seen).split("\n") == \
        clipboard_out.normalize_to_lf(original).split("\n")


@pytest.mark.parametrize("name", sorted(ALL_CASES))
def test_copy_out_preserves_blank_lines_and_indentation(name):
    original = ALL_CASES[name]
    seen_lines = clipboard_out.normalize_to_lf(_copy_out(original)).split("\n")
    original_lines = clipboard_out.normalize_to_lf(original).split("\n")
    assert seen_lines == original_lines
    # No line was trimmed, and no line was merged into its neighbour.
    assert len(seen_lines) == len(original_lines)
    for got, want in zip(seen_lines, original_lines):
        assert got == want


def test_lf_only_content_gains_exactly_one_cr_per_break():
    lf_text = "https://example.com/a\nhttps://example.com/b"
    assert _copy_out(lf_text) == "https://example.com/a\r\nhttps://example.com/b"


def test_capture_to_copy_round_trip_through_the_vault(vault):
    """Full path: capture -> storage -> retrieval -> copy back out."""
    for name, original in sorted(ALL_CASES.items()):
        clip = vault.capture(original, source_app="probe.exe", force=True)
        assert clip is not None, name
        stored = vault.storage.get_clip(clip.id).content
        # Storage is byte-verbatim; nothing is normalised on the way in.
        assert stored == original, name
        retrieved = vault.copied_again(clip.id)
        assert retrieved == original, name
        assert _copy_out(retrieved) == \
            clipboard_out.canonical_clipboard_text(original), name


# --- the two writers must agree ------------------------------------------------

def test_set_clipboard_text_writes_the_canonical_form(monkeypatch):
    """Quick Paste/macro path must put the same bytes on the clipboard as copy."""
    written: list[tuple[int, str]] = []
    fake = types.ModuleType("win32clipboard")
    fake.OpenClipboard = lambda *a: None
    fake.CloseClipboard = lambda *a: None
    fake.EmptyClipboard = lambda *a: None
    fake.SetClipboardData = lambda fmt, data: written.append((fmt, data))
    monkeypatch.setitem(sys.modules, "win32clipboard", fake)
    monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True)

    assert paste_delivery.set_clipboard_text("a\nb") is True
    assert written[-1][1] == "a\r\nb"

    assert paste_delivery.set_clipboard_text(CASE_A) is True
    assert written[-1][1] == clipboard_out.canonical_clipboard_text(CASE_A)
    assert "\r\r" not in written[-1][1]


def test_both_paths_produce_identical_clipboard_bytes(monkeypatch):
    written: list[str] = []
    fake = types.ModuleType("win32clipboard")
    fake.OpenClipboard = lambda *a: None
    fake.CloseClipboard = lambda *a: None
    fake.EmptyClipboard = lambda *a: None
    fake.SetClipboardData = lambda _fmt, data: written.append(data)
    monkeypatch.setitem(sys.modules, "win32clipboard", fake)
    monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True)

    for original in ALL_CASES.values():
        paste_delivery.set_clipboard_text(original)
        assert written[-1] == _copy_out(original)


def test_restore_clipboard_text_stays_byte_exact(monkeypatch):
    """A snapshot belonging to the user or another app must come back as found."""
    written: list[str] = []
    fake = types.ModuleType("win32clipboard")
    fake.OpenClipboard = lambda *a: None
    fake.CloseClipboard = lambda *a: None
    fake.EmptyClipboard = lambda *a: None
    fake.SetClipboardData = lambda _fmt, data: written.append(data)
    monkeypatch.setitem(sys.modules, "win32clipboard", fake)
    monkeypatch.setattr(paste_delivery, "_HAS_WIN32", True)

    odd = "kept\rverbatim\n\r\nexactly"
    assert paste_delivery.restore_clipboard_text(odd) is True
    assert written[-1] == odd


# --- Combine fidelity ---------------------------------------------------------

def test_compose_text_preserves_interior_whitespace():
    part = "line one\n\nline three  \n\tindented"
    for mode in ("newline", "blank_line", "numbered", "markdown_bullets"):
        out = compose_text([part, "second"], mode)
        assert "line one\n\nline three  \n\tindented" in out, mode


def test_compose_text_boundary_is_exactly_one_separator():
    # Trailing/leading newlines at the edges must not stack with the separator.
    assert compose_text(["a\n\n", "\n\nb"], "newline") == "a\nb"
    assert compose_text(["a\n\n", "\n\nb"], "blank_line") == "a\n\nb"
    # ...while interior blank lines of each part still survive.
    assert compose_text(["a\n\nb\n", "c"], "newline") == "a\n\nb\nc"


def test_compose_text_keeps_edge_spaces_and_tabs():
    assert compose_text(["a  ", "  b"], "newline") == "a  \n  b"
    assert compose_text(["a\t\n", "\n\tb"], "newline") == "a\t\n\tb"


def test_compose_text_prefixes_first_line_only():
    assert compose_text(["x\ny", "z"], "numbered") == "1. x\ny\n2. z"
    assert compose_text(["x\ny", "z"], "markdown_bullets") == "- x\ny\n- z"


def test_compose_text_skips_whitespace_only_parts():
    assert compose_text(["a", "   \n\t ", "b"], "newline") == "a\nb"
    assert compose_text(["   ", ""], "newline") == ""


def test_compose_text_does_not_collapse_url_lines():
    parts = ["https://example.com/a\r\nhttps://example.com/b", "https://example.com/c"]
    out = compose_text(parts, "newline")
    assert clipboard_out.normalize_to_lf(out).split("\n") == [
        "https://example.com/a", "https://example.com/b", "https://example.com/c",
    ]


def test_combined_text_survives_the_copy_path():
    combined = compose_text([CASE_A, CASE_B], "blank_line")
    seen = _copy_out(combined)
    assert "\r\r" not in seen
    assert clipboard_out.normalize_to_lf(seen) == clipboard_out.normalize_to_lf(combined)


# --- the real production copy paths -------------------------------------------
# The tests above characterise the shared helper. These drive the actual UI
# entry points, so a regression at any individual call site is caught too.

def _app_stub(clips=None):
    """A CacheVaultApp with only the clipboard/monitor collaborators stubbed."""
    from types import SimpleNamespace

    from cache_vault.ui.shell import CacheVaultApp

    store = dict(clips or {})
    app = object.__new__(CacheVaultApp)
    app._clipboard: list[str] = []
    app._toasts: list[str] = []
    app._copied_content: list[str] = []
    app._selected_clip_ids = list(store)
    app._guard_unlocked = lambda: True
    app.clipboard_clear = lambda: app._clipboard.clear()
    app.clipboard_append = lambda s: app._clipboard.append(s)
    app._show_toast = lambda msg: app._toasts.append(msg)
    app._monitor = SimpleNamespace(
        note_local_copy=lambda s: app._copied_content.append(s),
        note_local_copy_image=lambda _i: None,
    )
    app.vault = SimpleNamespace(
        storage=SimpleNamespace(
            get_clip=store.get,
            load_clip_asset_bytes=lambda _cid: None,
        ),
        copied_again=lambda cid: store[cid].content,
        events=SimpleNamespace(record=lambda *a, **k: None),
    )
    return app


def _clipboard_seen_by_windows(app) -> str:
    return _as_windows_clipboard("".join(app._clipboard))


@pytest.mark.parametrize("name", sorted(ALL_CASES))
def test_copy_text_entry_point_preserves_structure(name):
    original = ALL_CASES[name]
    app = _app_stub()
    app._copy_text(original)
    seen = _clipboard_seen_by_windows(app)
    assert "\r\r" not in seen
    assert seen == clipboard_out.canonical_clipboard_text(original)
    # The monitor must be told what is really on the clipboard.
    assert app._copied_content == [seen]


def test_copy_generated_text_entry_point_preserves_structure():
    app = _app_stub()
    app._copy_generated_text(CASE_B, "Copied.")
    seen = _clipboard_seen_by_windows(app)
    assert "\r\r" not in seen
    assert seen == clipboard_out.canonical_clipboard_text(CASE_B)
    assert app._copied_content == [seen]


def test_bulk_copy_of_multiline_clips_preserves_structure(monkeypatch):
    """Batch copy of two multi-line CRLF clips: the reported reproduction."""
    from types import SimpleNamespace

    from cache_vault.core import editable_copies, models

    monkeypatch.setattr(
        editable_copies, "write_file_receipt", lambda *a, **k: None)

    def _clip(cid, content):
        return SimpleNamespace(
            id=cid, classification=models.CLASS_PLAIN,
            content_type=models.CONTENT_TEXT, content=content, title=None)

    app = _app_stub({"c1": _clip("c1", CASE_A), "c2": _clip("c2", CASE_C)})
    app._bulk_copy_format("plain")

    seen = _clipboard_seen_by_windows(app)
    assert "\r\r" not in seen, "an extra CR is the reported extra blank line"
    lines = clipboard_out.normalize_to_lf(seen).split("\n")
    # Both clips arrive whole, one blank line between them, nothing merged.
    assert lines == (clipboard_out.normalize_to_lf(CASE_A).split("\n")
                     + [""] + clipboard_out.normalize_to_lf(CASE_C).split("\n"))
    assert app._copied_content == [seen]


# --- multi-link receipt -------------------------------------------------------

def test_multi_link_raw_text_is_verbatim():
    """The receipt clip is documented as the original raw paste."""
    raw = "\n  https://a.test/1.zip \r\n\r\nhttps://b.test/2.zip  \n"
    payload = multi_link.detect_multi_link_payload(raw)
    assert payload is not None
    assert payload.raw_text == raw
    assert payload.urls == ("https://a.test/1.zip", "https://b.test/2.zip")
