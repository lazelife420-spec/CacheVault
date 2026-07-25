"""First-use vault briefing — explains receipts, Safes, Mobile Inbox, and exports."""

from __future__ import annotations

from typing import Callable, Literal

import customtkinter as ctk

from .. import brand
from . import theme
from .guide_copy import (
    GUIDE_BTN_DISMISS,
    GUIDE_BTN_RECEIPTS,
    GUIDE_BTN_START,
    GUIDE_CARDS,
    GUIDE_SUBTITLE,
    GUIDE_TITLE,
)


def _bring_to_front(win: ctk.CTkToplevel) -> None:
    win.update_idletasks()
    win.lift()
    win.attributes("-topmost", True)
    win.after(200, lambda: win.attributes("-topmost", False))
    win.focus_force()


GuideAction = Literal["start", "receipts", "dismiss"]


class FirstUseGuideDialog(ctk.CTkToplevel):
    """Scrollable intro shown once (or again from Settings)."""

    def __init__(
        self,
        master,
        *,
        from_settings: bool,
        on_action: Callable[[GuideAction], None],
    ):
        # Track every self.after(...) job this window schedules -- including
        # CustomTkinter's own internal calls, since super().__init__() itself
        # triggers both the Windows titlebar-color workaround and its own
        # titlebar-icon workaround (each scheduling a delayed callback)
        # before this constructor body ever runs. Must be installed before
        # super().__init__() so those calls are covered too; see
        # _cancel_pending_after_jobs for why this exists and why that -- not
        # an overridden destroy() -- is the right hook.
        self._pending_after_ids: set[str] = set()
        self.after = self._tracked_after
        super().__init__(master)
        # <Destroy> is Tk's own event, fired for every destruction path --
        # including when this window is torn down as a side effect of its
        # parent's destroy() cascading at the Tcl level, which never calls a
        # Python-level destroy() override on this object at all (confirmed:
        # CacheVaultApp.destroy() ends with a plain super().destroy(), it
        # does not loop over winfo_children() calling each child's .destroy()
        # -- that cascade happens inside Tk/Tcl, invisibly to Python). An
        # overridden destroy() alone would therefore miss exactly the
        # real-world sequence that reproduced this bug (see issue #78):
        # CacheVaultApp auto-opens this dialog at 150ms, then gets destroyed
        # itself while the dialog's own delayed callbacks are still pending.
        self.bind("<Destroy>", self._cancel_pending_after_jobs, add="+")
        self.title(GUIDE_TITLE)
        self.geometry("560x640")
        self.resizable(False, True)
        self.minsize(520, 520)
        self._on_action = on_action
        self._from_settings = from_settings

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(side="bottom", fill="x", padx=16, pady=(4, 14))
        ctk.CTkButton(
            footer, text=GUIDE_BTN_START,
            command=lambda: self._done("start"),
            **theme.primary_button(),
        ).pack(fill="x", pady=3)
        ctk.CTkButton(
            footer, text=GUIDE_BTN_RECEIPTS,
            command=lambda: self._done("receipts"),
            **theme.secondary_button(),
        ).pack(fill="x", pady=3)
        ctk.CTkButton(
            footer, text=GUIDE_BTN_DISMISS,
            command=lambda: self._done("dismiss"),
            fg_color="transparent",
            hover_color=theme.nav_hover_bg(),
            text_color=brand.MUTED_FG,
        ).pack(fill="x", pady=(2, 0))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(side="top", fill="both", expand=True, padx=12, pady=(12, 4))

        ctk.CTkLabel(
            scroll, text=GUIDE_TITLE,
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=brand.PROOF_TEAL,
        ).pack(anchor="w", pady=(4, 4))
        ctk.CTkLabel(
            scroll, text=GUIDE_SUBTITLE,
            anchor="w", justify="left", wraplength=500,
            text_color=brand.MUTED_FG, font=theme.body_font(12),
        ).pack(anchor="w", pady=(0, 14))

        for idx, (title, body) in enumerate(GUIDE_CARDS, start=1):
            card = ctk.CTkFrame(scroll, fg_color=brand.SURFACE_BG, corner_radius=8)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(
                card, text=f"{idx}. {title}",
                anchor="w", font=ctk.CTkFont(size=13, weight="bold"),
            ).pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                card, text=body,
                anchor="w", justify="left", wraplength=480,
                text_color=brand.MUTED_FG, font=theme.body_font(11),
            ).pack(fill="x", padx=12, pady=(0, 10))

        self.protocol("WM_DELETE_WINDOW", self._close_only)
        self.transient(master)
        _bring_to_front(self)

    def _tracked_after(self, ms, fn=None, *args):
        """Replaces self.after for the lifetime of this window (see __init__).

        Tk's Misc.after(ms, fn, *args) returns an id but nothing tracks it;
        destroy() needs to know every id this window has outstanding -- both
        ours (_bring_to_front's topmost-reset) and CustomTkinter's own
        internal ones -- so it can cancel them instead of leaving them to
        fire against an already-destroyed widget.
        """
        if fn is None:
            # The no-callback form (self.after(ms): just sleeps) isn't used
            # by anything that touches this window, but delegate straight
            # through rather than silently changing that method's behavior.
            return super().after(ms)

        job_id = None

        def _run_and_untrack():
            self._pending_after_ids.discard(job_id)
            fn(*args)

        job_id = super().after(ms, _run_and_untrack)
        self._pending_after_ids.add(job_id)
        return job_id

    def _cancel_pending_after_jobs(self, event=None) -> None:
        """Bound to <Destroy> in __init__: cancel every self.after(...) job
        this window scheduled, however teardown actually happened.

        CustomTkinter's Windows dark-titlebar workaround
        (resizable() -> after(10ms) -> _windows_set_titlebar_color() ->
        after(5ms) -> _revert_withdraw_after_windows_set_titlebar_color(),
        plus a focus-restore after(1ms)), its titlebar-icon workaround
        (after(200ms) iconbitmap), and this dialog's own _bring_to_front()
        (after(200ms) topmost-reset) all schedule delayed callbacks. If any
        are still pending when this widget is actually destroyed, Tk raises
        "invalid command name" once each fires -- reproduced twice,
        consecutively, in full-suite runs (see issue #78). <Destroy> fires at
        the moment Tk tears the widget down, while the interpreter can still
        cancel a pending `after` id, regardless of whether that happened via
        an explicit .destroy() call or a parent window's destroy() cascading
        through Tcl.

        Must filter to this widget's own event: <Destroy> bound on a
        Toplevel fires for every descendant too, as each is torn down in the
        same cascade (Tk's default bindtags for any widget include its
        containing toplevel's path, so a Toplevel-level binding matches
        descendant events as well as its own) -- confirmed empirically, a
        full construct-then-destroy cycle produces 67 <Destroy> events for
        this dialog's widget subtree, only 1 of which is the dialog's own.
        Without filtering, destroying so much as a single descendant button
        while this dialog is still fully alive and open (winfo_exists() still
        true) wipes every tracked pending job -- silently cancelling
        legitimate in-flight titlebar/focus/icon/topmost-reset work that has
        nothing to do with teardown.

        An earlier version filtered with `event.widget is not self`, which
        broke cancellation entirely: event.widget is not reliably
        `is`-identical to self at destroy time (it can be a resolved widget
        object or a bare Tcl path string depending on internal registry
        state), so that guard's early-return branch was always taken and
        nothing ever got cancelled. Comparing the *string* Tk path instead
        (str(event.widget) against self._w, this widget's own stable path)
        is reliable regardless of which form event.widget takes -- verified
        empirically to correctly flag exactly the 1-of-67 self event.
        """
        if event is not None and str(event.widget) != self._w:
            return  # a descendant's own <Destroy>, not this window's
        for job_id in list(self._pending_after_ids):
            try:
                self.after_cancel(job_id)
            except Exception:  # noqa: BLE001 - already fired/invalid, fine
                pass
        self._pending_after_ids.clear()

    def _done(self, action: GuideAction) -> None:
        self._on_action(action)
        self.destroy()

    def _close_only(self) -> None:
        if self._from_settings:
            self.destroy()
            return
        self._on_action("start")
        self.destroy()
