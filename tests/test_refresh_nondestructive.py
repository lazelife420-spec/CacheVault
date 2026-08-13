"""Non-destructive refresh + refreshing-indicator behavior.

Before this, refresh() destroyed every list/grid row synchronously (via
_show_loading_skeleton), before the 50ms debounce even fired -- i.e.
before any DB work started. That's what produced the reported "list goes
blank" symptom, independent of how long the subsequent DB work took.
refresh() must now leave existing content on screen (and _visible_clip_ids
unchanged) until a fresh snapshot has actually been applied, with only a
small non-blocking indicator signaling that a refresh is in flight.
"""

from __future__ import annotations

import pytest

from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault
from cache_vault.ui.shell import CacheVaultApp
from tests.tk_support import _tcl_unavailable, probe_tk_ui, wait_for_refresh

OK, REASON = probe_tk_ui()
pytestmark = pytest.mark.skipif(not OK, reason=REASON)


def _make_app(n_clips: int = 10):
    vault = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    for i in range(n_clips):
        vault.capture(f"clip {i}", force=True)
    try:
        app = CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable: {exc}")
        raise
    app.withdraw()
    return app


def _wait_for_indicator_to_settle(app) -> None:
    wait_for_refresh(
        app,
        ui_settled=lambda: app._page_header._refreshing_label.place_info() == {},
        ui_description="refreshing label place_info() is empty",
    )


def _refresh_generation(app) -> int:
    gen = getattr(app, "_refresh_generation", 0)
    return gen if isinstance(gen, int) else 0


def _refresh_diagnostics(app) -> str:
    label = app._page_header._refreshing_label
    return (
        f"generation={getattr(app, '_refresh_generation', None)!r}, "
        f"render_active={getattr(app, '_render_active', None)!r}, "
        f"workers_in_flight={getattr(app, '_refresh_workers_in_flight', None)!r}, "
        f"refresh_job={getattr(app, '_refresh_job', None)!r}, "
        f"pending_signature={getattr(app, '_pending_refresh_signature', None)!r}, "
        f"label_text={label.cget('text')!r}, "
        f"label_place_info={label.place_info()!r}"
    )


def _start_owned_refresh_and_wait(
    app,
    *,
    ui_settled,
    ui_description: str,
    timeout: float = 6.0,
    max_timeout: float | None = None,
) -> int:
    """Request a refresh and guarantee the request starts a NEW generation.

    The refresh-indicator tests must observe the generation started by their
    own scripted failure/success refresh -- not an automatic refresh (resize
    debounce, first-use initialization, ...) that may already be render-active.

    ``shell.refresh()`` intentionally *coalesces* a call made while a render is
    active into ``_pending_refresh_signature`` without bumping
    ``_refresh_generation``.  A naive ``app.refresh()`` + ``wait_for_refresh``
    can therefore end up observing an unrelated, already-active generation --
    one that may have been started (with the real connection) *before* the test
    installed its failure, complete successfully, hide the indicator, and let
    ``wait_for_refresh`` return before the intended failure generation ever
    runs.  That is the proven test-isolation defect this helper closes.

    This helper calls ``app.refresh()`` and *directly observes* whether that
    exact call incremented ``_refresh_generation`` (no event pumping happens
    between reading the generation, calling ``refresh()``, and reading it
    again, so the increment is attributable to this call alone):

    * if the generation did **not** increment, the call was coalesced into an
      active render -- the helper waits (via the existing ``wait_for_refresh``)
      for that render to finish, then retries;
    * if the generation **did** increment, that generation is recorded as the
      test-owned target and the helper waits for its completion *and* for the
      caller-supplied UI postcondition before returning.

    All work runs inside a single bounded monotonic deadline; there are no
    fixed-duration sleeps used as proof of completion, and normal Tk event
    pumping is preserved through ``wait_for_refresh``.  The started generation
    is returned.  Ownership is never inferred merely because the application
    eventually becomes idle -- only a directly observed
    ``after_generation > before_generation`` is accepted.
    """
    import time

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if max_timeout is None:
        max_timeout = timeout * 3
    if max_timeout < timeout:
        raise ValueError("max_timeout cannot be shorter than timeout")

    deadline = time.monotonic() + max_timeout
    coalesced_attempts = 0

    while True:
        before = _refresh_generation(app)
        app.refresh()
        after = _refresh_generation(app)
        if after > before:
            started = after
            break

        # The call was coalesced: a render is already active, so refresh()
        # recorded the request as pending instead of bumping the generation.
        coalesced_attempts += 1
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise AssertionError(
                "refresh request never started a new generation "
                f"(coalesced {coalesced_attempts} time(s) into an active "
                f"render); before={before}, after={after}, "
                f"{_refresh_diagnostics(app)}"
            )
        # Let the active render finish (render_active -> False) so the next
        # refresh() call is not coalesced, then retry.
        wait_for_refresh(
            app,
            timeout=min(timeout, remaining),
            max_timeout=remaining,
            ui_settled=lambda: not getattr(app, "_render_active", False),
            ui_description="active render to finish before retrying owned refresh",
        )

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise AssertionError(
            "started a new refresh generation but no time remained to observe "
            f"its result; started_generation={started}, "
            f"{_refresh_diagnostics(app)}"
        )
    try:
        wait_for_refresh(
            app,
            timeout=min(timeout, remaining),
            max_timeout=remaining,
            ui_settled=ui_settled,
            ui_description=ui_description,
        )
    except AssertionError as exc:
        raise AssertionError(
            f"owned refresh generation {started} did not reach the required UI "
            f"state ({ui_description}); {_refresh_diagnostics(app)}\n"
            f"underlying: {exc}"
        ) from exc
    return started


def test_refresh_leaves_visible_clips_untouched_before_debounce_fires():
    app = _make_app(10)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        before = list(app._visible_clip_ids)
        assert before, "precondition: something is actually shown"

        app.refresh()
        # No app.update() / wait here on purpose: this checks the state
        # immediately after refresh() returns, before the 50ms debounce
        # timer (let alone the worker thread) has had any chance to run.
        assert app._visible_clip_ids == before, (
            "refresh() must not clear rendered state before new data is ready"
        )
        assert len(app._list.winfo_children()) > 0 or len(app._grid.winfo_children()) > 0

        wait_for_refresh(app)
    finally:
        app.destroy()


def test_page_header_shows_refreshing_indicator_while_in_flight():
    for _iteration in range(30):
        app = _make_app(5)
        try:
            app._navigate_screen(S.FILTER_ALL)
            _wait_for_indicator_to_settle(app)
            assert app._page_header._refreshing_label.place_info() == {}

            app.refresh()
            assert app._page_header._refreshing_label.cget("text") == "Refreshing…"

            _wait_for_indicator_to_settle(app)
            assert app._page_header._refreshing_label.place_info() == {}
        finally:
            app.destroy()


def test_refresh_failure_shows_error_indicator_and_keeps_old_content(monkeypatch):
    app = _make_app(6)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)
        before_ids = list(app._visible_clip_ids)
        before_children = len(app._list.winfo_children()) + len(app._grid.winfo_children())
        assert before_ids

        def boom(*a, **k):
            raise RuntimeError("simulated vault read failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)

        # Start a refresh generation that the test actually owns (i.e. one that
        # begins AFTER the failure connection is installed) and wait until the
        # error indicator is visible.  A plain app.refresh() here can be
        # coalesced into an already-active (pre-failure, successful) refresh, so
        # the intended failure generation would never run -- see
        # _start_owned_refresh_and_wait.
        _start_owned_refresh_and_wait(
            app,
            ui_settled=lambda: (
                "failed" in app._page_header._refreshing_label.cget("text").lower()
                and app._page_header._refreshing_label.place_info() != {}
            ),
            ui_description="error indicator visible after a failed refresh",
        )

        assert app._visible_clip_ids == before_ids, "old content must survive a failed refresh"
        assert (
            len(app._list.winfo_children()) + len(app._grid.winfo_children())
        ) == before_children
        assert "failed" in app._page_header._refreshing_label.cget("text").lower()
        assert app._page_header._refreshing_label.place_info() != {}
    finally:
        app.destroy()


def test_successful_refresh_after_a_failure_clears_the_error_indicator(monkeypatch):
    app = _make_app(4)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)

        def boom(*a, **k):
            raise RuntimeError("simulated failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)
        # Own the failure generation so the visible error indicator is the
        # result of THIS scripted failure, not of an unrelated active refresh.
        _start_owned_refresh_and_wait(
            app,
            ui_settled=lambda: (
                "failed" in app._page_header._refreshing_label.cget("text").lower()
                and app._page_header._refreshing_label.place_info() != {}
            ),
            ui_description="error indicator visible after a failed refresh",
        )
        assert app._page_header._refreshing_label.place_info() != {}

        monkeypatch.undo()
        # Own the recovery generation (started after the connection is
        # restored) and wait until the error indicator is cleared.
        _start_owned_refresh_and_wait(
            app,
            ui_settled=lambda: app._page_header._refreshing_label.place_info() == {},
            ui_description="refreshing/error indicator hidden after recovery",
        )
        assert app._page_header._refreshing_label.place_info() == {}
    finally:
        app.destroy()


def test_owned_refresh_helper_recovers_when_scripted_refresh_is_coalesced(monkeypatch):
    """Deterministic regression for the proven test-isolation defect.

    With a render already active, an ordinary ``app.refresh()`` is coalesced
    into ``_pending_refresh_signature`` without bumping ``_refresh_generation``
    -- so a naive refresh()+wait would observe the unrelated active generation
    (which, having started before the failure was installed, succeeds and hides
    the indicator).  ``_start_owned_refresh_and_wait`` must retry past that
    coalescing and start a DISTINCT failure generation whose visible error
    indicator the test can assert on.

    This drives the exact defect deterministically (no reliance on random
    resize/first-use timing) using only the app's own refresh machinery -- no
    production refresh logic is copied, rewritten, or altered.
    """
    app = _make_app(5)
    try:
        app._navigate_screen(S.FILTER_ALL)
        wait_for_refresh(app)

        # Put the app into the "already render-active" state the defect
        # requires, using its own machinery: refresh() schedules the render and
        # _do_refresh_sync() (which its own docstring notes tests may call
        # directly to skip the 50ms debounce) starts the active render + an
        # in-flight worker.  Nothing pumps the main thread here, so the render
        # stays active until wait_for_refresh() runs inside the helper below.
        app.refresh()
        app._do_refresh_sync()
        assert app._render_active is True, "precondition: a render must be active"

        # An ordinary refresh in this state is coalesced: no new generation,
        # and the request is recorded as pending instead.
        gen_before = app._refresh_generation
        app.refresh()
        assert app._refresh_generation == gen_before, (
            "an ordinary refresh while render-active must coalesce, not start a "
            "new generation"
        )
        assert app._pending_refresh_signature is not None, (
            "the coalesced request must be recorded as a pending signature"
        )

        # Install the failure and use the owned-refresh helper.  It must retry
        # past the coalescing and start a DISTINCT failure generation.
        def boom(*a, **k):
            raise RuntimeError("simulated vault read failure")

        monkeypatch.setattr(app.vault.storage, "reader_connection", boom)

        started = _start_owned_refresh_and_wait(
            app,
            ui_settled=lambda: (
                "failed" in app._page_header._refreshing_label.cget("text").lower()
                and app._page_header._refreshing_label.place_info() != {}
            ),
            ui_description="error indicator visible after a coalesced failure",
        )

        assert started > gen_before, (
            "the helper must start a generation distinct from the coalesced "
            f"attempt (started={started}, gen_before={gen_before})"
        )
        assert "failed" in app._page_header._refreshing_label.cget("text").lower()
        assert app._page_header._refreshing_label.place_info() != {}
    finally:
        app.destroy()
