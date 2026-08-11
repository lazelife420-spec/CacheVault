"""Regression: searching while a large-vault batch render is still building
must supersede that render cleanly, leaving neither stale rows nor stranded
refresh state.

The large-vault optimization renders a capped clip set in chunked
``after(5, ...)`` batches so the UI thread never blocks, and relies on the
render's ``on_complete`` callback to hand ownership back to the shell
(``_finish_active_refresh`` clears ``_render_active`` and runs at most one
trailing refresh). Generation tokens were meant to make a superseded render
stop immediately.

They did stop it -- silently. An abandoned chain returned early on the
generation check and therefore never reached ``on_complete``, so the shell's
``_render_active`` stayed True forever. Because ``refresh()`` returns early
while ``_render_active`` is True (recording only
``_pending_refresh_signature``, whose sole consumer is
``_finish_active_refresh``), every subsequent refresh was swallowed and the
view froze part-way through the abandoned query: partially built rows, header
counts belonging to the old query, and a stuck busy indicator. Measured
directly against the unfixed code by abandoning a 120-row render at row 31:
``on_complete`` ran 0 times, ``_render_active`` stayed True, and four
following ``refresh()`` calls left the rendered set pinned at 31 rows with
the previous query's 120 visible ids. The same corruption was reproduced on
the packaged build by typing a search term during the initial All Clips
render.

The contract asserted here: exactly one of ``on_complete`` / ``on_superseded``
fires for every ``render_batched`` call, and a snapshot older than the one
already rendered is refused outright rather than repainting over newer
results. The shell-level tests assert the user-visible invariant that follows
from it -- search during an active batch render ends up showing exactly the
new query's results, with the full search text intact and no render
ownership left held.

Nothing here proves correctness by wall-clock waiting: the supersede is
injected from inside ``_build_row`` at a chosen row index, so the render is
abandoned mid-chain on every run regardless of machine speed.
"""

import pytest
import customtkinter as ctk

from cache_vault.core.models import Clip, now_iso
from cache_vault.ui.clip_grid import ClipGrid
from cache_vault.ui.clip_list import ClipList
from cache_vault.ui.shell import MAX_VISIBLE_CLIPS
from tests.tk_support import probe_tk_ui
from tests.test_clip_render_cap import (  # noqa: PLC2701 - shared Tk fixtures
    _make_app,
    _settle,
    _vault_with_clips,
)

OK, REASON = probe_tk_ui()

pytestmark = pytest.mark.skipif(not OK, reason=REASON)

ABANDON_AT_ROW = 24


def _clips(count: int) -> list[Clip]:
    return [
        Clip(
            id=f"clip-{i}",
            content_type="text",
            content=f"Clip content {i}",
            created_at=now_iso(),
            updated_at=now_iso(),
        )
        for i in range(count)
    ]


@pytest.fixture
def root():
    r = ctk.CTk()
    r.withdraw()
    yield r
    r.destroy()


# --- view-level completion contract ---------------------------------------

@pytest.mark.parametrize("view_factory", [ClipList, ClipGrid])
def test_abandoned_render_reports_superseded_instead_of_complete(root, view_factory):
    completed, superseded = [], []
    view = view_factory(root, on_select=lambda _clip: None)
    try:
        view.render_batched(
            _clips(100),
            on_complete=lambda: completed.append(1),
            on_superseded=lambda: superseded.append(1),
        )
        assert view._render_job is not None, "chain should still be in flight"

        view.cancel_render()

        assert completed == [], "an abandoned render must not report completion"
        assert superseded == [1], "abandonment must be reported exactly once"
    finally:
        view.destroy()


@pytest.mark.parametrize("view_factory", [ClipList, ClipGrid])
def test_completed_render_reports_completion_exactly_once(root, view_factory):
    completed, superseded = [], []
    view = view_factory(root, on_select=lambda _clip: None)
    try:
        view.render_batched(
            _clips(24),
            on_complete=lambda: completed.append(1),
            on_superseded=lambda: superseded.append(1),
        )
        for _ in range(200):
            root.update()
            if view._render_job is None:
                break

        assert completed == [1]
        assert superseded == []

        # A cancel after the chain already finished has no owner to notify.
        view.cancel_render()
        assert superseded == []
        assert completed == [1]
    finally:
        view.destroy()


@pytest.mark.parametrize("view_factory", [ClipList, ClipGrid])
def test_superseding_render_releases_the_previous_owner(root, view_factory):
    first, second = [], []
    view = view_factory(root, on_select=lambda _clip: None)
    try:
        view.render_batched(
            _clips(100), generation=1,
            on_complete=lambda: first.append("complete"),
            on_superseded=lambda: first.append("superseded"),
        )
        view.render_batched(
            _clips(100), generation=2,
            on_complete=lambda: second.append("complete"),
            on_superseded=lambda: second.append("superseded"),
        )

        assert first == ["superseded"], "the replaced render must release ownership"
        assert second == [], "the new render is still building"
    finally:
        view.destroy()


@pytest.mark.parametrize("view_factory", [ClipList, ClipGrid])
def test_stale_generation_snapshot_is_refused(root, view_factory):
    stale = []
    view = view_factory(root, on_select=lambda _clip: None)
    try:
        view.render_batched(_clips(16), generation=7)
        for _ in range(200):
            root.update()
            if view._render_job is None:
                break
        rendered = list(view._render_order)

        # A worker result from an older generation arriving late must not
        # repaint over the newer results already on screen.
        view.render_batched(
            _clips(80), generation=6,
            on_complete=lambda: stale.append("complete"),
            on_superseded=lambda: stale.append("superseded"),
        )

        assert stale == ["superseded"]
        assert list(view._render_order) == rendered, "newer results were overwritten"
        assert view._render_job is None, "a refused render must not start a chain"
    finally:
        view.destroy()


# --- shell-level invariant -------------------------------------------------

def _pump_until(app, predicate, seconds=15.0):
    """Pump the real Tk loop until ``predicate`` holds.

    The sleep matters: refresh snapshots come back from the worker thread
    through _call_on_main, which the shell drains from a 50ms _pump_main_thread
    timer. A tight update() loop can burn hundreds of iterations inside a
    single 50ms window and never let that timer fire at all.
    """
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        app.update()
        if predicate():
            return True
        time.sleep(0.005)
    return False


def _abandon_render_at(app, view, row):
    """Fire ``action`` from inside the chain, once ``row`` rows are built."""
    state = {"fired": False}
    build_row = view._build_row

    def wrapper(clip):
        result = build_row(clip)
        if not state["fired"] and len(view._render_order) >= row:
            state["fired"] = True
            view.cancel_render()
        return result

    view._build_row = wrapper
    return state


def test_render_ownership_is_released_when_a_batch_chain_is_abandoned(tmp_path):
    """The mechanism: an abandoned chain must not strand _render_active, or
    every later refresh is swallowed and the view stays frozen mid-render.
    """
    from cache_vault.core.storage import FILTER_ALL

    vault = _vault_with_clips(tmp_path, 300, prefix="item")
    app = _make_app(vault)
    try:
        _settle(app)
        app._navigate_screen(FILTER_ALL)
        _settle(app)

        state = _abandon_render_at(app, app._list, ABANDON_AT_ROW)
        app.refresh(immediate=True)
        assert _pump_until(app, lambda: state["fired"]), (
            "the render was never abandoned mid-chain"
        )
        _pump_until(app, lambda: not app._render_active, seconds=5.0)

        assert app._render_active is False, (
            "abandoned render left ownership held; every later refresh would "
            "be swallowed into _pending_refresh_signature forever"
        )

        # Ownership released means a following refresh actually renders.
        app._search_var.set("item 49")
        app.refresh()
        _settle(app)
        assert len(app._visible_clip_ids) > 0
    finally:
        app.destroy()
        vault.close()


def test_collapsing_a_group_mid_render_does_not_strand_refresh_state(tmp_path):
    """A real, reachable user path into the same defect.

    Clicking a date-group header calls ClipList._toggle_group -> render() ->
    clear() -> cancel_render() synchronously, bypassing refresh() and its
    _render_active guard entirely. Doing that while the capped All Clips
    render is still building abandons the chain, and before the fix that
    stranded render ownership for the rest of the session: Search, Refresh
    and navigation all became no-ops behind the frozen partial list.
    """
    from cache_vault.core.storage import FILTER_ALL

    vault = _vault_with_clips(tmp_path, 300, prefix="item")
    app = _make_app(vault)
    try:
        _settle(app)
        app._navigate_screen(FILTER_ALL)
        _settle(app)

        titles = []
        build_group_header = app._list._build_group_header

        def header_spy(group_by, title, count):
            titles.append((group_by, title))
            return build_group_header(group_by, title, count)

        app._list._build_group_header = header_spy

        state = {"fired": False}
        build_row = app._list._build_row

        def wrapper(clip):
            result = build_row(clip)
            if not state["fired"] and titles and len(app._list._render_order) >= ABANDON_AT_ROW:
                state["fired"] = True
                app._list._toggle_group(*titles[0])
            return result

        app._list._build_row = wrapper
        app.refresh(immediate=True)
        pumped = _pump_until(app, lambda: state["fired"])
        app._list._build_row = build_row
        app._list._build_group_header = build_group_header
        if not pumped:
            pytest.skip("this vault produced no grouped clip-list render to collapse")

        _pump_until(app, lambda: not app._render_active, seconds=5.0)
        assert app._render_active is False, (
            "collapsing a group mid-render stranded render ownership"
        )

        app._search_var.set("item 49")
        app.refresh()
        _settle(app)
        expected = [c.id for c in vault.list_clips(app._build_query(),
                                                   limit=MAX_VISIBLE_CLIPS)]
        assert app._visible_clip_ids == expected, "search after the abandon was lost"
    finally:
        app.destroy()
        vault.close()


def test_search_during_active_batch_render_shows_only_the_new_query(tmp_path):
    """The acceptance contract: typing a search term while a large-vault
    render is still building leaves the full search text in place and the
    view showing exactly that query's results -- no stale rows, no stale
    counts, no render ownership left held.
    """
    from cache_vault.core.storage import FILTER_ALL

    term = "item 49"
    vault = _vault_with_clips(tmp_path, 300, prefix="item")
    app = _make_app(vault)
    try:
        _settle(app)
        app._navigate_screen(FILTER_ALL)
        _settle(app)
        assert len(app._visible_clip_ids) == MAX_VISIBLE_CLIPS

        # Search lands while the (capped) All Clips render is mid-chain.
        state = {"fired": False}
        build_row = app._list._build_row

        def wrapper(clip):
            result = build_row(clip)
            if not state["fired"] and len(app._list._render_order) >= ABANDON_AT_ROW:
                state["fired"] = True
                app._search_var.set(term)
                app.refresh(immediate=True)
            return result

        app._list._build_row = wrapper
        app.refresh(immediate=True)
        assert _pump_until(app, lambda: state["fired"]), "search never landed mid-render"

        app._list._build_row = build_row
        _settle(app)

        expected = [c.id for c in vault.list_clips(app._build_query(),
                                                   limit=MAX_VISIBLE_CLIPS)]
        assert expected, "fixture must produce a non-empty result set"

        assert app._search_var.get() == term, "search text was corrupted"
        assert app._render_active is False, "render ownership was left held"
        assert app._pending_refresh_signature is None, "a refresh was left unrun"
        assert app._visible_clip_ids == expected, "view shows stale results"
        assert len(app._list._render_order) == len(expected), (
            "rows left over from the superseded render"
        )
    finally:
        app.destroy()
        vault.close()


def test_repeated_search_edits_during_render_settle_on_the_last_query(tmp_path):
    """Rapid successive edits during rendering: only the final query may own
    the rendered result set."""
    from cache_vault.core.storage import FILTER_ALL

    vault = _vault_with_clips(tmp_path, 300, prefix="item")
    app = _make_app(vault)
    try:
        _settle(app)
        app._navigate_screen(FILTER_ALL)
        _settle(app)

        for term in ("item 1", "item 12", "item 123"):
            app._search_var.set(term)
            app.refresh(immediate=True)
            # Enough pumping for the render to start, never enough to finish:
            # each edit lands while the previous one is still building rows.
            _pump_until(app, lambda: app._list._render_job is not None, seconds=5.0)

        _settle(app)

        expected = [c.id for c in vault.list_clips(app._build_query(),
                                                   limit=MAX_VISIBLE_CLIPS)]
        assert app._search_var.get() == "item 123"
        assert app._render_active is False
        assert app._visible_clip_ids == expected
        assert len(app._list._render_order) == len(expected)
    finally:
        app.destroy()
        vault.close()
