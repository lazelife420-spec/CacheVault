"""CTkTextbox subclass containing CustomTkinter's own untracked,
perpetually-rescheduling scrollbar-visibility poll.

CTkTextbox.__init__ schedules ``self.after(50, self._check_if_scrollbars_needed,
None, True)``, and _check_if_scrollbars_needed itself reschedules every 200ms
via ``self.after(self._scrollbar_update_time, lambda: ...)`` for as long as the
widget is alive (see ctk_textbox.py in the installed customtkinter package).
Neither call's returned id is ever stored, so CTkTextbox.destroy() (which
itself does nothing but forward to the base class) has no way to cancel
whichever poll is currently pending. A textbox destroyed -- directly or via a
parent's teardown cascade at the Tcl level, which never calls a Python-level
destroy() on children at all -- while that poll is still pending leaves Tk to
report "invalid command name" once it fires against the now-destroyed widget
(issue #79).

Every CacheVault call site that constructs a CTkTextbox should use
CacheVaultTextbox instead so this containment applies uniformly rather than
being fixed ad hoc per call site.
"""

from __future__ import annotations

import customtkinter as ctk


class CacheVaultTextbox(ctk.CTkTextbox):
    def __init__(self, *args, **kwargs):
        self._scrollbar_check_job: str | None = None
        # CTkTextbox.__init__ (invoked by super().__init__() below) schedules
        # its own first scrollbar-check poll via self.after(50, ...) before
        # this constructor's own body runs. Overriding self.after only for
        # the duration of super().__init__() captures that one call the same
        # way CacheVaultApp captures CTk's root titlebar-icon job (see
        # cache_vault/ui/shell.py _capture_titlebar_icon_job / issue #80);
        # the override is removed immediately after super().__init__()
        # returns, so nothing else self.after(...)'s during construction is
        # affected.
        self.after = self._capture_initial_scrollbar_check_job
        try:
            super().__init__(*args, **kwargs)
        finally:
            del self.after

    def _capture_initial_scrollbar_check_job(self, ms, fn=None, *args):
        job_id = super().after(ms) if fn is None else super().after(ms, fn, *args)
        if fn is not None and fn == self._check_if_scrollbars_needed:
            self._scrollbar_check_job = job_id
        return job_id

    def _check_if_scrollbars_needed(self, event=None, continue_loop: bool = False) -> None:
        """Overrides CTkTextbox's own method so its self.after(...) reschedule
        (ctk_textbox.py) never runs -- that call's returned id is discarded
        there and could never be tracked or cancelled. This class takes over
        scheduling the recurring poll itself, tracking whichever id is
        CURRENTLY pending in self._scrollbar_check_job, while still running
        the exact same show/hide logic via super() so scrollbar behavior is
        unchanged while the widget is alive.

        continue_loop is True only for the initial self.after(50, ...) call
        from CTkTextbox.__init__ (captured above) and for this class's own
        reschedule firing (_reschedule_scrollbar_check) -- never for the
        direct, on-demand calls CTkTextbox.edit_redo()/edit_undo() make (both
        pass no continue_loop, defaulting to False). Only in the continue_loop
        case is the invocation itself "consuming" whichever job was tracked,
        so only then is it safe to clear/replace the tracked id -- otherwise
        an on-demand edit_redo()/edit_undo() call while a recurring poll is
        already pending would wrongly discard the reference needed to cancel
        that still-live job later.
        """
        if continue_loop:
            self._scrollbar_check_job = None
        super()._check_if_scrollbars_needed(event, continue_loop=False)
        if continue_loop and self._textbox.winfo_exists():
            self._scrollbar_check_job = self.after(
                self._scrollbar_update_time, self._reschedule_scrollbar_check,
            )

    def _reschedule_scrollbar_check(self) -> None:
        self._check_if_scrollbars_needed(continue_loop=True)

    def destroy(self) -> None:
        if self._scrollbar_check_job is not None:
            try:
                self.after_cancel(self._scrollbar_check_job)
            except Exception:
                pass
            self._scrollbar_check_job = None
        super().destroy()
