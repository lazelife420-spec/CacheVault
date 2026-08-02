"""Regression: the clip list must cap how many rows it materialises, and the
refresh pipeline that fills it must not duplicate work.

Each rendered row is a deep CustomTkinter tree (~45 Tk widgets, each a Windows
USER object). An unbounded history exhausts the ~10,000 per-process USER-object
quota and makes Tk raise "No more menus can be allocated" on the next menu,
which froze multi-clip copy. The shell caps rendering at MAX_VISIBLE_CLIPS and
surfaces the remainder, instead of rendering the whole vault.

The refresh-coalescing tests below guard a related, previously-real defect:
refresh() used to cancel and restart an already-active render (worker DB
query in flight, or its resulting widget batch still building) whenever
another call landed mid-render -- e.g. a window-resize/layout-mode change
during ordinary app startup. Direct measurement against unmodified code
showed this restarting a 120-row capped render from scratch, producing 149
row builds and 2 full storage queries for a single logical refresh, and
occasionally missing the settlement deadline outright. Confirmed via a
controlled interleaved comparison (identical test, identical environment):
unmodified code reproduced 149 row builds / 2 storage queries / generations
[2, 4] in every trial; the fix produced exactly 120 row builds / 1 storage
query / generation [2] in every trial, 10/10 clean runs.

Two layers of coalescing exist, and are tested at two different levels:

1. Debounce/generation coalescing (self._refresh_job / self._refresh_
   generation / self.after / self.after_cancel) -- rapid-fire refresh()
   calls *before* any of them has started rendering collapse into one
   debounce timer. This is pre-existing behavior, unchanged by the fix
   below. Proven deterministically using _FakeScheduler, a test-only
   instance-level stand-in for self.after()/self.after_cancel() -- no
   wall-clock, no timeout-based polling as the proof mechanism.

2. Active-render coalescing (self._render_active / self._pending_refresh_
   signature / self._finish_active_refresh) -- a refresh() call that lands
   *while* a previous one is already rendering (worker query in flight, or
   its widget batch still building) does not cancel/restart that render;
   it just records the latest requested state, and _finish_active_refresh
   fires at most one trailing refresh once the active render completes,
   only if that recorded state actually differs from what was just shown.
   This is the fix itself. Proven deterministically too: _do_refresh_sync()
   sets _render_active True synchronously, before the (real) worker thread
   is even started, and nothing in these tests pumps the Tk event loop
   until they deliberately choose to -- so _render_active's window is
   exactly as long as the test wants it to be, regardless of how fast the
   background worker thread actually runs. wait_for_refresh() is used only
   to drain the pipeline to completion afterward, never as the mechanism
   that proves coalescing happened.

Only test_large_history_is_capped is a real Tk-timer/render integration
test (it lets an actual debounce timer and actual after(10, ...) render
batches run to completion via wait_for_refresh) -- everything else below
proves the state machine directly.
"""

import pytest

from cache_vault.ui.shell import CacheVaultApp, MAX_VISIBLE_CLIPS
from tests.tk_support import probe_tk_ui, _tcl_unavailable, wait_for_refresh  # noqa: PLC2701

OK, REASON = probe_tk_ui()


def _make_app(vault):
    try:
        return CacheVaultApp(vault=vault)
    except Exception as exc:  # noqa: BLE001
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk runtime unavailable at app construction: {exc}")
        raise


def _vault_with_clips(tmp_path, n, prefix="clip"):
    from cache_vault.core.storage import VaultStorage
    from cache_vault.core.settings import Settings
    from cache_vault.core.vault import Vault

    # capture_paused=True keeps CacheVaultApp's live ClipboardMonitor from
    # auto-capturing whatever happens to be on the real OS clipboard during
    # the test -- confirmed to happen without this: a stray real-clipboard
    # capture landed mid-test, producing one more stored clip than this
    # fixture deliberately wrote, intermittently inflating "exactly n clips"
    # assertions. first_use_guide_dismissed=True similarly keeps a real
    # FirstUseGuideDialog (shell.py ~line 4770) from popping up 150ms after
    # construction and synchronously re-entering the Tk event loop from
    # inside its own CTk init -- unrelated noise these tests have no
    # interest in.
    settings = Settings(capture_paused=True, first_use_guide_dismissed=True)
    vault = Vault(storage=VaultStorage(tmp_path / "vault.db"), settings=settings)
    for i in range(n):
        vault.capture(f"{prefix} {i} https://example{i}.com/path", force=True)
    return vault


def _settle(app) -> None:
    """Drain whatever refresh is already in flight to a *truly* idle state
    before a test installs the fake scheduler / starts spying.

    Construction kicks off one refresh() itself (shell.py ~line 434) and
    _navigate_screen() triggers another -- both expected. Less obviously, a
    live window's first real <Configure> event recomputes the responsive
    layout mode and, the first time only, calls refresh() as a further,
    unrelated side effect once its own 150ms debounce elapses (see
    _on_window_configure/_handle_resize_debounced/_apply_layout_mode,
    shell.py ~line 3001-3053) -- and that can still be scheduled-but-not-yet
    -fired at the exact moment a single wait_for_refresh() call observes an
    earlier generation settle and returns (a real race between two
    independently-timed real Tk timers). One wait_for_refresh() call is
    therefore not reliable proof that no further refresh() is about to
    fire on its own; loop it until the app is actually fully idle (job
    cleared, no worker in flight, both queues empty, no render active, no
    pending signature) before any test starts treating what follows as its
    own controlled measurement window. This is a test-setup concern, not a
    substitute for real-time waiting inside the measurement itself --
    nothing below this point depends on wall-clock elapsed time to prove
    coalescing.
    """
    for _ in range(10):
        wait_for_refresh(app)
        if (
            app._refresh_job is None
            and app._refresh_workers_in_flight == 0
            and app._refresh_request_queue.qsize() == 0
            and app._main_thread_calls.qsize() == 0
            and getattr(app, "_resize_job", None) is None
            and getattr(app, "_render_active", False) is False
            and getattr(app, "_pending_refresh_signature", None) is None
        ):
            return
    raise AssertionError(
        "app did not reach a fully idle refresh state before test setup"
    )


def test_cap_constant_is_safe():
    # ~45 Tk/USER objects per row; stay well under the 10k Windows quota with
    # headroom for menus, dialogs, and the preview pane.
    assert 0 < MAX_VISIBLE_CLIPS <= 200


@pytest.mark.skipif(not OK, reason=REASON)
def test_large_history_is_capped(tmp_path):
    """Real Tk-timer/render integration test: an actual debounce timer and
    actual chunked after(10, ...) render batches run to completion. Also
    guards the active-render-coalescing fix directly: an uncoalesced
    restart of this exact scenario (a window-resize refresh landing mid-
    render) previously produced 149 row builds / 2 storage queries instead
    of the 120 row builds / 1 storage query asserted here.
    """
    from unittest import mock

    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, MAX_VISIBLE_CLIPS + 30)

    app = _make_app(vault)
    try:
        # Patch the bound instance methods, not the class: wrapping the
        # unbound class function would drop `self` on every call routed
        # through the mock (MagicMock is not a descriptor), silently
        # corrupting the call and diverting it into the worker's failure
        # path instead of actually exercising the code under test.
        with mock.patch.object(
            vault, "list_clips", wraps=vault.list_clips,
        ) as list_clips_mock, mock.patch.object(
            app._list, "_build_row", wraps=app._list._build_row,
        ) as build_row_mock, mock.patch.object(
            vault, "capture", wraps=vault.capture,
        ) as capture_mock:
            app.withdraw()
            app._navigate_screen(S.FILTER_ALL)
            # refresh() is debounced — call _do_refresh_sync() directly to
            # skip the debounce timer. The DB read + render still happen on
            # a worker thread and get applied via after(), so wait for that
            # to settle before asserting on _visible_clip_ids. wait_for_
            # refresh's own model-settled signal fires as soon as
            # _apply_refresh_snapshot returns, which for a chunked render is
            # only after the *first* batch, so the extra ui_settled
            # condition polls _render_active/_render_job directly to make
            # sure every batch has actually been built (and any resize-
            # triggered active-render-coalescing has resolved) before the
            # mock call counts below are checked. This is a
            # MAX_VISIBLE_CLIPS-row render (up to ~150 batched rows), so
            # give it real headroom rather than the small-vault default.
            app._do_refresh_sync()
            wait_for_refresh(
                app,
                timeout=25.0,
                ui_settled=lambda: (
                    app._render_active is False
                    and app._list._render_job is None
                    and app._refresh_job is None
                ),
                ui_description="capped render (and any trailing refresh) fully settled",
            )

            assert len(app._visible_clip_ids) == MAX_VISIBLE_CLIPS
            actual_total = len(vault.storage.list_clips())
            assert actual_total == MAX_VISIBLE_CLIPS + 30
            assert app._list._more_count == actual_total - MAX_VISIBLE_CLIPS

            # Exactly one effective storage query and one row-build pass —
            # not the 2 queries / 149 builds an uncoalesced restart produces.
            assert list_clips_mock.call_count == 1
            assert build_row_mock.call_count == MAX_VISIBLE_CLIPS

            # No stray auto-capture from a live clipboard monitor landed
            # while the app was constructing/navigating/rendering.
            assert capture_mock.call_count == 0
    finally:
        app.destroy()


# ---------------------------------------------------------------------------
# Deterministic refresh-coalescing regressions.
#
# A small instance-level fake scheduler stands in for self.after()/
# self.after_cancel() on exactly one app instance so refresh()'s debounce
# timer becomes an inspectable dict entry instead of a real Tk timer --
# see _FakeScheduler below. refresh()/_do_refresh_sync() themselves are
# never stubbed; only the after()/after_cancel() plumbing underneath them
# is faked. The active-render-coalescing tests (contracts A/B) don't even
# need the fake scheduler for their core assertions: _do_refresh_sync()
# flips _render_active to True synchronously, before the real worker
# thread starts, and since nothing pumps the Tk event loop until a test
# explicitly calls wait_for_refresh(), the background worker's actual
# speed can never leak into the window under test.
# ---------------------------------------------------------------------------


class _FakeScheduler:
    """Deterministic instance-level stand-in for ``self.after`` /
    ``self.after_cancel`` on one already-constructed ``CacheVaultApp``.

    Job identity is a plain incrementing counter -- no wall-clock, no
    ``time.time()``/``time.monotonic()`` is ever consulted. "Firing" a job
    means calling its target function directly and synchronously from test
    code; nothing here sleeps or polls.

    Install/restore mirrors ``CacheVaultApp._capture_titlebar_icon_job``
    (cache_vault/ui/shell.py ~line 252-256): an instance-level attribute
    shadows the class's real (Tk-bound) ``after``/``after_cancel`` while
    installed, and ``restore()`` simply deletes that instance attribute so
    ordinary attribute lookup falls back to the real, class-bound method --
    it does not need to save a separate reference to "the real after" to do
    this correctly, since Python's attribute lookup already does that via
    the class descriptor once the instance override is gone.
    """

    def __init__(self, app):
        self._app = app
        self._counter = 0
        self._pending: dict[str, tuple[int, object, tuple]] = {}
        self._cancelled: set[str] = set()
        self._executed: set[str] = set()
        self._installed = False

    # -- install/restore ----------------------------------------------------

    def install(self) -> None:
        if self._installed:
            raise AssertionError("fake scheduler already installed")
        self._app.after = self.after
        self._app.after_cancel = self.after_cancel
        self._installed = True

    def restore(self) -> None:
        if not self._installed:
            return
        del self._app.after
        del self._app.after_cancel
        self._installed = False

    # -- fake after() / after_cancel() ---------------------------------------

    def after(self, ms, fn=None, *args):
        self._counter += 1
        job_id = f"fake-after-{self._counter}"
        if fn is not None:
            self._pending[job_id] = (ms, fn, args)
        return job_id

    def after_cancel(self, job_id) -> None:
        # Real Tk's after_cancel() is a harmless no-op for an id that has
        # already fired or was never valid -- production code (e.g.
        # _do_refresh_sync defensively cancelling its own, already-consumed
        # job id) relies on that not raising, so mirror it here too.
        self._pending.pop(job_id, None)
        self._cancelled.add(job_id)

    # -- test-driving API -----------------------------------------------------

    def run(self, job_id):
        """Execute exactly one pending job's callback, synchronously."""
        if job_id in self._cancelled:
            raise AssertionError(f"refusing to run cancelled job {job_id!r}")
        if job_id in self._executed:
            raise AssertionError(f"refusing to run job {job_id!r} a second time")
        if job_id not in self._pending:
            raise KeyError(f"no such pending fake job: {job_id!r}")
        _delay, fn, args = self._pending.pop(job_id)
        self._executed.add(job_id)
        return fn(*args)

    def was_cancelled(self, job_id) -> bool:
        return job_id in self._cancelled

    @property
    def pending_ids(self) -> list[str]:
        return list(self._pending)

    @property
    def pending_count(self) -> int:
        return len(self._pending)


@pytest.mark.skipif(not OK, reason=REASON)
def test_fake_scheduler_contract(tmp_path):
    """Contract test of the fake scheduler harness itself, independent of
    refresh()/CacheVaultApp: a cancelled job can never fire, and no job can
    fire twice. (Proves: cancelled-job-never-fires, in isolation.)
    """
    vault = _vault_with_clips(tmp_path, 0)
    app = _make_app(vault)
    try:
        app.withdraw()
        _settle(app)

        fake = _FakeScheduler(app)
        fake.install()
        try:
            calls = []

            job_a = fake.after(50, calls.append, "a")
            fake.after_cancel(job_a)
            assert fake.was_cancelled(job_a)
            with pytest.raises(AssertionError):
                fake.run(job_a)
            assert calls == []  # cancelled job never ran

            job_b = fake.after(50, calls.append, "b")
            fake.run(job_b)
            assert calls == ["b"]
            with pytest.raises((KeyError, AssertionError)):
                fake.run(job_b)
            assert calls == ["b"]  # second attempt did not run it again
        finally:
            fake.restore()
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_refresh_calls_coalesce_deterministically(tmp_path):
    """refresh() debounces rapid-fire calls into exactly one applied
    generation -- proven via the fake scheduler instead of real elapsed
    time. (Proves: scheduled-debounce coalescing; also demonstrates
    cancelled-job-never-fires in context, against real refresh() calls.)
    """
    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        # Baseline measured from the actually-settled state rather than a
        # hardcoded literal: the vault fixture inserts n=5, but this must
        # not assume nothing else could ever be visible under FILTER_ALL --
        # it only asserts that our coalesced refresh reproduces whatever
        # was already correctly showing, not a re-derived guess at the count.
        expected_visible_count = len(app._visible_clip_ids)
        assert expected_visible_count == 5

        collected: list[tuple[int, str, object]] = []
        orig_collect = app._collect_refresh_snapshot

        def _spy_collect(gen, active, query):
            collected.append((gen, active, query))
            return orig_collect(gen, active, query)

        app._collect_refresh_snapshot = _spy_collect

        applied: list[int] = []
        orig_apply = app._apply_refresh_snapshot

        def _spy_apply(gen, active, query, counts, clips, total_clips):
            applied.append(gen)
            return orig_apply(gen, active, query, counts, clips, total_clips)

        app._apply_refresh_snapshot = _spy_apply

        try:
            start_gen = app._refresh_generation
            assert app._refresh_job is None

            fake = _FakeScheduler(app)
            fake.install()
            try:
                # Rapid-fire calls, same filter/query state, before any of
                # them has fired.
                app.refresh()
                job_1 = app._refresh_job
                app.refresh()
                job_2 = app._refresh_job
                app.refresh()
                job_3 = app._refresh_job

                # Never more than one live job at a time: each call cancelled
                # the previous one and scheduled a fresh one.
                assert len({job_1, job_2, job_3}) == 3
                assert fake.pending_count == 1
                assert fake.pending_ids == [job_3]
                assert fake.was_cancelled(job_1)
                assert fake.was_cancelled(job_2)
                assert app._refresh_job == job_3
                assert app._refresh_generation == start_gen + 3

                # The two superseded jobs can never fire, even if something
                # still held a reference to them.
                with pytest.raises(AssertionError):
                    fake.run(job_1)
                with pytest.raises(AssertionError):
                    fake.run(job_2)

                # Fire the one retained job -- this calls the real
                # _do_refresh_sync(), which hands off to the real
                # background worker thread/queue (no Tk timers there).
                fake.run(job_3)
                assert app._refresh_job is None
                with pytest.raises((KeyError, AssertionError)):
                    fake.run(job_3)
            finally:
                fake.restore()

            # From here the real Tk pump (already scheduled since
            # construction, untouched by the fake scheduler) drives the
            # worker-thread hand-off and the chunked render batches to
            # completion.
            wait_for_refresh(
                app,
                ui_settled=lambda: (
                    app._render_active is False and app._list._render_job is None
                ),
                ui_description="clip list render batch complete",
            )

            final_gen = app._refresh_generation
            assert final_gen == start_gen + 3

            assert len(collected) == 1  # exactly one storage query
            gen0, active0, _query0 = collected[0]
            assert gen0 == final_gen
            assert active0 == S.FILTER_ALL

            assert applied == [final_gen]  # exactly one generation applied
            assert len(app._visible_clip_ids) == expected_visible_count

            assert app._refresh_job is None
            assert app._render_active is False
            assert app._list._render_job is None
            assert app._refresh_request_queue.qsize() == 0
            assert app._refresh_workers_in_flight == 0
        finally:
            del app._collect_refresh_snapshot
            del app._apply_refresh_snapshot
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_refresh_coalesces_to_latest_filter_not_first(tmp_path):
    """Two refresh() calls for *different* filter/query states, back to
    back before the debounce fires, must still collapse into a single
    applied generation -- and that generation must reflect the *latest*
    state, never the first (stale) one it started from. (Proves:
    latest-filter-wins, at the pre-render debounce layer.)
    """
    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        collected: list[tuple[int, str, object]] = []
        orig_collect = app._collect_refresh_snapshot

        def _spy_collect(gen, active, query):
            collected.append((gen, active, query))
            return orig_collect(gen, active, query)

        app._collect_refresh_snapshot = _spy_collect

        try:
            fake = _FakeScheduler(app)
            fake.install()
            try:
                app.refresh()  # signature: FILTER_ALL
                job_first = app._refresh_job

                # Change context directly -- no _navigate_screen(), which
                # would issue its own refresh() and muddy "exactly two
                # refresh() calls with two different signatures".
                app._filters.set_active(S.FILTER_FAVORITES)
                app.refresh()  # signature: FILTER_FAVORITES
                job_second = app._refresh_job

                assert job_first != job_second
                assert fake.was_cancelled(job_first)
                assert fake.pending_count == 1

                with pytest.raises(AssertionError):
                    fake.run(job_first)

                fake.run(job_second)
            finally:
                fake.restore()

            wait_for_refresh(
                app,
                ui_settled=lambda: (
                    app._render_active is False and app._list._render_job is None
                ),
                ui_description="clip list render batch complete",
            )

            assert len(collected) == 1
            gen0, active0, _query0 = collected[0]
            assert active0 == S.FILTER_FAVORITES  # latest, not FILTER_ALL
            assert gen0 == app._refresh_generation
        finally:
            del app._collect_refresh_snapshot
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_stale_snapshot_is_discarded_after_supersession(tmp_path):
    """A refresh snapshot that lands after a newer refresh() has already
    bumped the generation past it must be discarded, not painted -- proven
    directly against _apply_refresh_snapshot's/_apply_refresh_failure's
    staleness guard. No threads or timers needed: the guard is plain
    Python state comparison. (Proves: stale-snapshot-discard.)
    """
    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, 3)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        before_ids = list(app._visible_clip_ids)
        workers_before = app._refresh_workers_in_flight

        stale_gen = app._refresh_generation  # the "in-flight" generation

        # A newer refresh() supersedes it before its snapshot lands.
        fake = _FakeScheduler(app)
        fake.install()
        try:
            app.refresh()
            assert app._refresh_generation == stale_gen + 1
        finally:
            fake.restore()

        # Simulate the stale worker's snapshot landing late. Bogus payload
        # is fine: the staleness guard returns before any of it is touched.
        sentinel_calls = []
        orig_update_counts = app._filters.update_counts
        app._filters.update_counts = lambda *a, **k: sentinel_calls.append((a, k))
        try:
            app._refresh_workers_in_flight += 1
            app._apply_refresh_snapshot(
                stale_gen, S.FILTER_ALL, None, {}, object(), object(),
            )
        finally:
            app._filters.update_counts = orig_update_counts

        # Discarded: no UI work happened, in-flight counter still balances.
        assert sentinel_calls == []
        assert app._visible_clip_ids == before_ids
        assert app._refresh_workers_in_flight == workers_before

        # A stale failure callback is equally inert.
        app._refresh_workers_in_flight += 1
        app._apply_refresh_failure(stale_gen, RuntimeError("stale"))
        assert app._refresh_workers_in_flight == workers_before
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_equivalent_request_during_active_render_is_suppressed(tmp_path):
    """Contract A: a refresh() call whose effective signature is identical
    to the one currently rendering (_render_active already True) must not
    cancel or restart it: no second worker query, no second render, and
    once the active render finishes, _finish_active_refresh finds the
    recorded pending signature equal to what was just rendered and fires
    no trailing refresh at all.

    _do_refresh_sync() sets _render_active True synchronously as part of
    firing the retained fake job -- before the real worker thread has done
    anything -- and nothing here pumps the Tk event loop until the final
    wait_for_refresh() call, so the window in which _render_active is True
    is exactly as long as this test wants it to be; the real worker
    thread's actual speed can't race it.
    """
    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        collected: list[int] = []
        orig_collect = app._collect_refresh_snapshot

        def _spy_collect(gen, active, query):
            collected.append(gen)
            return orig_collect(gen, active, query)

        app._collect_refresh_snapshot = _spy_collect

        applied: list[int] = []
        orig_apply = app._apply_refresh_snapshot

        def _spy_apply(gen, active, query, counts, clips, total_clips):
            applied.append(gen)
            return orig_apply(gen, active, query, counts, clips, total_clips)

        app._apply_refresh_snapshot = _spy_apply

        try:
            start_gen = app._refresh_generation
            assert app._render_active is False

            fake = _FakeScheduler(app)
            fake.install()
            try:
                app.refresh()
                job = app._refresh_job
                assert job is not None
                fake.run(job)  # -> real _do_refresh_sync(): _render_active = True
            finally:
                fake.restore()

            assert app._render_active is True
            assert app._refresh_generation == start_gen + 1
            rendering_gen = app._refresh_generation

            # Same active/query/view_mode as what's already rendering.
            app.refresh()

            # Recorded as pending immediately -- refresh() can't yet know it
            # will turn out equivalent -- but the active generation must be
            # completely untouched: no cancel, no restart, no new job.
            assert app._pending_refresh_signature is not None
            assert app._refresh_generation == rendering_gen
            assert app._render_active is True
            assert app._refresh_job is None  # no debounce job was scheduled

            # Further identical calls change nothing further.
            app.refresh()
            app.refresh()
            assert app._refresh_generation == rendering_gen
            assert app._render_active is True
            assert app._refresh_job is None

            wait_for_refresh(
                app,
                ui_settled=lambda: (
                    app._render_active is False
                    and app._list._render_job is None
                    and app._refresh_job is None
                ),
                ui_description="active render settles with no trailing refresh",
            )

            # Exactly one query, one render -- the equivalent request(s)
            # never queued a second worker call or a second render.
            assert collected == [rendering_gen]
            assert applied == [rendering_gen]

            # Equivalent to what was just rendered: cleared without
            # triggering a trailing refresh. Generation never moved again.
            assert app._pending_refresh_signature is None
            assert app._refresh_generation == rendering_gen
            assert app._refresh_job is None
            assert app._refresh_request_queue.qsize() == 0
            assert app._refresh_workers_in_flight == 0
        finally:
            del app._collect_refresh_snapshot
            del app._apply_refresh_snapshot
    finally:
        app.destroy()


@pytest.mark.skipif(not OK, reason=REASON)
def test_material_requests_during_active_render_yield_one_trailing_refresh(tmp_path):
    """Contract B: several *different*-signature refresh() calls arriving
    while a render is active must collapse to exactly one recorded pending
    signature (the latest), let the active generation finish normally, and
    then fire exactly one trailing refresh whose result reflects the
    latest requested state -- not an intermediate one.
    """
    from cache_vault.core import storage as S

    vault = _vault_with_clips(tmp_path, 5)
    app = _make_app(vault)
    try:
        app.withdraw()
        app._navigate_screen(S.FILTER_ALL)
        _settle(app)

        collected: list[tuple[int, str]] = []
        orig_collect = app._collect_refresh_snapshot

        def _spy_collect(gen, active, query):
            collected.append((gen, active))
            return orig_collect(gen, active, query)

        app._collect_refresh_snapshot = _spy_collect

        applied: list[int] = []
        orig_apply = app._apply_refresh_snapshot

        def _spy_apply(gen, active, query, counts, clips, total_clips):
            applied.append(gen)
            return orig_apply(gen, active, query, counts, clips, total_clips)

        app._apply_refresh_snapshot = _spy_apply

        try:
            start_gen = app._refresh_generation

            fake = _FakeScheduler(app)
            fake.install()
            try:
                app.refresh()  # signature: FILTER_ALL
                job = app._refresh_job
                fake.run(job)  # -> real _do_refresh_sync(): _render_active = True
            finally:
                fake.restore()

            assert app._render_active is True
            rendering_gen = app._refresh_generation
            assert rendering_gen == start_gen + 1

            # Several different-signature requests while active -- none of
            # them may cancel/restart the active generation.
            app._filters.set_active(S.FILTER_FAVORITES)
            app.refresh()
            app._filters.set_active(S.FILTER_ALL)
            app.refresh()
            app._filters.set_active(S.FILTER_FAVORITES)
            app.refresh()

            assert app._refresh_generation == rendering_gen  # untouched
            assert app._render_active is True
            assert app._refresh_job is None  # no debounce job scheduled
            assert app._pending_refresh_signature is not None
            assert app._pending_refresh_signature[0] == S.FILTER_FAVORITES  # latest wins

            wait_for_refresh(
                app,
                timeout=10.0,
                ui_settled=lambda: (
                    app._render_active is False
                    and app._refresh_job is None
                    and app._list._render_job is None
                ),
                ui_description="active render plus its one trailing refresh both settle",
            )

            # The active render completed normally (its own query/apply),
            # then exactly one trailing refresh ran for the latest state --
            # not zero (dropped), not more than one (stacked).
            assert [gen for gen, _active in collected] == [rendering_gen, rendering_gen + 1]
            assert [a for _gen, a in collected] == [S.FILTER_ALL, S.FILTER_FAVORITES]
            assert applied == [rendering_gen, rendering_gen + 1]

            final_gen = app._refresh_generation
            assert final_gen == rendering_gen + 1  # exactly one trailing refresh

            assert app._filters.active == S.FILTER_FAVORITES
            assert app._pending_refresh_signature is None
            assert app._render_active is False
            assert app._refresh_job is None
            assert app._refresh_request_queue.qsize() == 0
            assert app._refresh_workers_in_flight == 0
        finally:
            del app._collect_refresh_snapshot
            del app._apply_refresh_snapshot
    finally:
        app.destroy()
