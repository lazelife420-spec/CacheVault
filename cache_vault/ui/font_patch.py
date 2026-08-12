"""Keep Tk font finalizers off background threads.

Every ``tkinter.font.Font`` (and therefore every ``CTkFont``) deletes its
underlying Tcl font in ``__del__``::

    def __del__(self):
        try:
            if self.delete_font:
                self._call("font", "delete", self.name)
        except Exception:
            pass

Two properties of that make it dangerous in a threaded app:

1.  ``__del__`` runs on whichever thread the garbage collector happens to be
    running on when the font becomes unreachable -- not necessarily the thread
    that created it, and not necessarily the main thread.
2.  It swallows every exception.  Calling into Tk from a non-main thread
    therefore does not fail loudly; it blocks on the Tcl interpreter.

The UI builds and discards large numbers of fonts (a clip render orphans well
over a thousand), so a garbage collection triggered on the refresh worker
thread while it is mid-query can run those finalizers there.  Observed as an
18 second stall with the refresh never settling and the worker parked inside a
sqlite call::

    refresh-worker
      shell._collect_refresh_snapshot -> vault.counts -> storage.counts
        -> sqlite3 execute(
        -> tkinter/font.py __del__ -> self._call("font", "delete", ...)

The guard installed here makes the finalizer a no-op unless it is running on
the main thread.  The cost of skipping is one leaked Tcl font name -- Tcl keeps
the font definition alive for the rest of the process.  That only happens for
fonts finalized off the main thread, which is rare; fonts released on the main
thread are still deleted normally.  A leaked name is strictly preferable to a
hung refresh.

``cache_vault.ui.theme.font`` avoids creating this garbage in the render hot
path in the first place; this guard covers every other font construction site
in the app, and any added later.
"""

from __future__ import annotations

import threading
from tkinter.font import Font

_ORIGINAL_DEL = None
_SKIPPED = 0


class FontPatchIncompatibleError(RuntimeError):
    """Installed tkinter.font.Font lacks the API the finalizer guard needs."""


def verify_font_patch_compatibility(font_cls=Font) -> None:
    """Verify Font exposes what the guard wraps, without installing anything.

    Only ``__del__`` is checked, because it is the only thing this module
    replaces and the only member verifiable without a Tk root. ``_call``,
    ``name`` and ``delete_font`` are instance attributes assigned in
    ``Font.__init__``, so they cannot be inspected on the class.

    Raises FontPatchIncompatibleError naming every missing attribute.
    """
    missing = [
        name for name in ("__del__",) if not hasattr(font_cls, name)
    ]
    if missing:
        raise FontPatchIncompatibleError(
            "tkinter.font.Font is missing "
            f"{', '.join(missing)}; the font finalizer guard cannot be "
            "installed safely against this Python build"
        )


def install_main_thread_font_finalizer_guard() -> None:
    """Make Font.__del__ a no-op off the main thread. Idempotent."""
    global _ORIGINAL_DEL
    if _ORIGINAL_DEL is not None:
        return
    verify_font_patch_compatibility()

    original = Font.__del__
    _ORIGINAL_DEL = original
    main_thread = threading.main_thread()

    def guarded_del(self):
        global _SKIPPED
        if threading.current_thread() is not main_thread:
            # Leak the Tcl font rather than calling Tk from this thread.
            _SKIPPED += 1
            return
        original(self)

    Font.__del__ = guarded_del


def skipped_finalizer_count() -> int:
    """Fonts whose Tcl delete was skipped because GC ran off the main thread.

    Diagnostic only. A non-zero value means the guard did its job.
    """
    return _SKIPPED


def _uninstall_for_tests() -> None:
    """Restore the original finalizer. Test-support only."""
    global _ORIGINAL_DEL, _SKIPPED
    if _ORIGINAL_DEL is not None:
        Font.__del__ = _ORIGINAL_DEL
        _ORIGINAL_DEL = None
    _SKIPPED = 0
