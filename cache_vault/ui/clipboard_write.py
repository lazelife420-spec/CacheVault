"""Route internal UI clipboard writes through the app's custody writer.

Dialogs and screens that only hold a widget reference use
:func:`write_text_via_app` to reach the single process-owned
``ClipboardWriter`` created by the shell (composition root). When no writer
is available (headless harnesses), the write falls back to the legacy plain
Tk clipboard write so behavior is unchanged.
"""

from __future__ import annotations

from ..core.clipboard_out import normalize_to_lf


def _tk_write(widget, text: str) -> bool:
    try:
        widget.clipboard_clear()
        # Tk's clipboard_append renders the selection itself and inserts a CR
        # before every LF, unconditionally -- text that already contains CRLF
        # would come back as CR CR LF. Feed it LF-only so its own CR-insertion
        # produces exactly one CRLF per line, matching clipboard_out.write_via_tk
        # and what ClipboardWriter.write_text's custody fingerprint expects.
        widget.clipboard_append(normalize_to_lf(text))
        return True
    except Exception:  # noqa: BLE001 - clipboard can be transiently locked
        return False


def resolve_clipboard_writer(widget):
    """The app's shared ClipboardWriter, or None when not wired."""
    try:
        return getattr(widget.winfo_toplevel(), "_clipboard_writer", None)
    except Exception:  # noqa: BLE001 - widget without a live Tk root
        return None


def write_text_via_app(widget, text: str, *, operation: str) -> bool:
    """Write ``text`` to the clipboard with self-capture custody when wired."""
    writer = resolve_clipboard_writer(widget)
    if writer is not None:
        return writer.write_text(text, operation=operation, via=lambda t: _tk_write(widget, t))
    return _tk_write(widget, text)
