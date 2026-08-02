"""Deterministic tests for the refresh generation guard.

_do_refresh_sync's DB work now runs on a worker thread and is applied on
the main thread via _apply_refresh_snapshot/_apply_refresh_failure. If two
refreshes overlap (a second refresh() call fires while an earlier worker is
still in flight -- e.g. rapid filter switching), the earlier worker's
result must never clobber state a newer refresh has already produced.

These call the REAL _apply_refresh_snapshot/_apply_refresh_failure methods
(not a reimplementation of the guard) against a bare object.__new__ stub, so
a regression in the actual guard clause fails these tests. self.vault is a
sentinel that raises if touched, so any test asserting "discarded" also
proves the method never got past the guard into real work.
"""

from __future__ import annotations

from types import SimpleNamespace

from cache_vault.ui.shell import CacheVaultApp


class _MustNotTouch:
    """Raises if any attribute is accessed -- stands in for self.vault to
    prove a discarded/guarded apply never reaches real work."""

    def __getattr__(self, name):
        raise AssertionError(f"guard did not short-circuit -- accessed vault.{name}")


def _app_stub(*, alive: bool = True, generation: int = 0):
    app = object.__new__(CacheVaultApp)
    app._refresh_generation = generation
    app._refresh_workers_in_flight = 0
    app._alive = lambda: alive
    app.vault = _MustNotTouch()
    # The except-path in _apply_refresh_snapshot/_apply_refresh_failure
    # flags the non-blocking header indicator; stub it out since these are
    # bare object.__new__ stubs with no real Tk widgets.
    app._page_header = SimpleNamespace(set_refreshing=lambda *a, **k: None)
    # Refresh-coalescing state that real CacheVaultApp.__init__ always sets
    # unconditionally (see shell.py __init__, alongside
    # _refresh_workers_in_flight) before any refresh()/_apply_refresh_*
    # call is reachable. This stub bypasses __init__ via object.__new__, so
    # without these, _apply_refresh_snapshot's `self._view_mode` read (and
    # _finish_active_refresh's `self._render_active`/
    # `self._pending_refresh_signature` reads) fall through to
    # tkinter.Misc.__getattr__ -> self.tk -> RecursionError, since self.tk
    # is also never set on this bare stub. Defaults mirror __init__ exactly.
    app._render_active = False
    app._pending_refresh_signature = None
    app._view_mode = "cards"
    return app


def test_stub_models_complete_refresh_coalescing_state():
    """Guards against this stub silently drifting out of sync with
    CacheVaultApp.__init__ again. object.__new__(CacheVaultApp) bypasses
    __init__ entirely, so every attribute _apply_refresh_snapshot or
    _finish_active_refresh touches on self (besides the ones already
    covered by other stubbed fields) must be explicitly set here with the
    same default __init__ gives a real instance -- otherwise access falls
    through to tkinter.Misc.__getattr__ and recurses into self.tk, which
    is also absent on a bare stub, producing a RecursionError instead of a
    clean AttributeError.
    """
    app = _app_stub()

    assert app._render_active is False
    assert app._pending_refresh_signature is None
    assert app._view_mode == "cards"


def test_stale_snapshot_is_discarded_without_touching_vault():
    app = _app_stub(generation=1)  # a newer refresh() already bumped this
    app._refresh_workers_in_flight = 1

    # Worker for generation 0 (older) finishes and tries to apply late.
    app._apply_refresh_snapshot(0, "all", None, {}, None, None)

    assert app._refresh_workers_in_flight == 0, "counter must still decrement"


def test_snapshot_for_dead_window_is_discarded_without_touching_vault():
    app = _app_stub(alive=False, generation=4)
    app._refresh_workers_in_flight = 1

    app._apply_refresh_snapshot(4, "all", None, {}, None, None)

    assert app._refresh_workers_in_flight == 0


def test_current_generation_snapshot_reaches_real_work(monkeypatch):
    """Sanity check the guard's positive case: a matching, alive generation
    must proceed past the guard (and therefore touch self.vault) -- proves
    the guard isn't accidentally discarding everything.

    _apply_refresh_snapshot catches and crash-logs exceptions from its body
    rather than raising (so one screen's bug can't take down the pump
    loop), so "reached real work" is observed via write_crash firing with
    the _MustNotTouch sentinel's message, not via a raised exception.
    """
    app = _app_stub(generation=7)
    app._refresh_workers_in_flight = 1
    crashes = []
    import cache_vault.ui.shell as shell_mod
    monkeypatch.setattr(shell_mod, "write_crash", lambda tag, exc: crashes.append((tag, exc)))

    app._apply_refresh_snapshot(7, "all", None, {}, None, None)

    assert app._refresh_workers_in_flight == 0, "counter decrements before the guard check"
    assert len(crashes) == 1 and "vault." in str(crashes[0][1]), (
        "a matching generation must reach real work (self.vault access), "
        "not be silently discarded"
    )


def test_stale_failure_is_discarded_and_not_logged(monkeypatch):
    app = _app_stub(generation=2)
    app._refresh_workers_in_flight = 1
    crashes = []
    import cache_vault.ui.shell as shell_mod
    monkeypatch.setattr(shell_mod, "write_crash", lambda tag, exc: crashes.append((tag, exc)))

    app._apply_refresh_failure(0, RuntimeError("stale worker error"))

    assert crashes == []
    assert app._refresh_workers_in_flight == 0


def test_current_generation_failure_is_logged(monkeypatch):
    app = _app_stub(generation=9)
    app._refresh_workers_in_flight = 1
    crashes = []
    import cache_vault.ui.shell as shell_mod
    monkeypatch.setattr(shell_mod, "write_crash", lambda tag, exc: crashes.append((tag, exc)))

    app._apply_refresh_failure(9, RuntimeError("real failure"))

    assert len(crashes) == 1
    assert crashes[0][0] == "refresh"
    assert app._refresh_workers_in_flight == 0


def test_overlapping_refreshes_only_the_newest_ever_reaches_real_work(monkeypatch):
    """Three refreshes fire in quick succession (rapid filter switching);
    only the last one's worker should ever get past the guard, regardless
    of the order their results arrive back on the main thread."""
    app = _app_stub(generation=0)
    crashes = []
    import cache_vault.ui.shell as shell_mod
    monkeypatch.setattr(shell_mod, "write_crash", lambda tag, exc: crashes.append((tag, exc)))

    # refresh() called three times rapidly, each bumping the generation
    # before the previous worker(s) finish.
    app._refresh_generation = 2
    app._refresh_workers_in_flight = 3

    # Generation 0 and 1 results arrive first (e.g. their DB work happened
    # to finish first) -- both must be silently discarded, no crash logged.
    app._apply_refresh_snapshot(0, "all", None, {}, None, None)
    app._apply_refresh_snapshot(1, "all", None, {}, None, None)
    assert app._refresh_workers_in_flight == 1
    assert crashes == []

    # Generation 2 (current) arrives last and must reach real work.
    app._apply_refresh_snapshot(2, "all", None, {}, None, None)
    assert app._refresh_workers_in_flight == 0
    assert len(crashes) == 1 and "vault." in str(crashes[0][1])
