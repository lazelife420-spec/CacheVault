"""Canonical text form for everything CacheVault puts on the Windows clipboard.

CacheVault writes the clipboard through two different mechanisms and they do not
agree, which is why the same multi-line clip could come back with an extra blank
line through one path and with no line break at all through the other:

* Tk's ``clipboard_append`` renders the selection itself and inserts a CR before
  *every* LF, unconditionally. Text that already contains CRLF -- which is what
  Windows apps put on the clipboard, and therefore what capture stores -- comes
  back as CR CR LF, which many apps show as an extra blank line. Measured, not
  assumed: ``'A\\r\\nB'`` is read back by another process as ``'A\\r\\r\\nB'``.
* ``win32clipboard.SetClipboardData(CF_UNICODETEXT, ...)`` (the paste-at-cursor
  and macro path) is byte-faithful, so LF-only text stays LF-only and Windows
  edit controls run the lines together.

Captured text is stored byte-verbatim, so neither writer can be handed the
stored string directly. Both are normalised through here instead: LF internally,
exactly one CRLF per line break on the clipboard, whichever writer runs.

Nothing else about the text is touched -- runs of spaces, tabs, indentation and
blank lines all survive, because only the line terminator representation
changes.
"""

from __future__ import annotations

import os


def normalize_to_lf(text: str) -> str:
    """Collapse CRLF and lone CR to LF, leaving all other characters alone."""
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def canonical_clipboard_text(text: str) -> str:
    """The exact string a Windows consumer reads back after ``text`` is copied."""
    return normalize_to_lf(text).replace("\n", "\r\n")


def write_via_tk(widget, text: str) -> str:
    """Copy ``text`` via Tk's clipboard; return what a reader will actually see.

    Tk is deliberately handed LF-only text because its renderer supplies the CR,
    so the clipboard ends up holding exactly one CRLF per line break.

    The return value is the string now on the clipboard, which is also what
    ``ClipboardMonitor.note_local_copy`` must be told: the monitor compares what
    it reads from the clipboard against that value, so passing it the unconverted
    source text made our own copy look like a brand new external clip and it got
    re-captured.
    """
    lf_text = normalize_to_lf(text)
    widget.clipboard_clear()
    widget.clipboard_append(lf_text)
    if os.name == "nt":
        return lf_text.replace("\n", "\r\n")
    return lf_text
