# Cache Vault — Gate B Receipt: MobileBridge Force-Stop Race

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT
**Scope:** narrow regression-first correctness fix only — not combined with E4b or any other cleanup.

## Baseline SHA

`6ec7bffbf487f3a07248e56fed9a19f5dade777f` (canonical `master`, closed at Gate A). Confirmed exact match, clean working tree, all Gate A + E1–E4a rollback tags intact, and `preservation/pre-gate5f-dirty-2026-08-20` unchanged before any work began.

## Rollback tag / branch

- `pre-gate-b-mobile-bridge-force-stop-2026-08-21` (points at baseline)
- `fix/gate-b-mobile-bridge-force-stop`

## Phase 1 — Reproduce before fix

**Command:** `python -m pytest tests/test_mobile_bridge.py::test_bridge_handle_stops_if_disabled -v`
**Result on pre-fix code, in isolation: PASSED** (0.14s) — this matches the audit's own observation that the test passes reliably in isolation and only fails under realistic scheduling contention.

**Current control flow at the time of reproduction** (`cache_vault/core/mobile/bridge.py::handle()`, lines 342–351, pre-fix):
```python
if not self.vault.settings.mobile_access_enabled:
    if self.is_running:
        import threading
        threading.Thread(
            target=self.stop,
            name="mobile-bridge-force-stop",
            daemon=True,
        ).start()
    rec = api_mod.reject_receipt(...)
    ...
    return 503, {"error": "mobile_access_disabled", ...}
```
`handle()` starts a daemon thread to call `self.stop()` and returns its 503 immediately — no `join()`, no `Event`, no future, nothing that would block the return until `stop()` has actually run. There is no synchronization primitive between `thread.start()` and the `return` statement.

**Structural (deterministic) proof, since real-world scheduling luck makes the race itself intermittent to hit by chance:** a throwaway script monkeypatched `bridge.stop` with a version that sleeps 0.05s (simulating realistic scheduling delay) before clearing `_server`, then called `handle()` and checked `is_running` immediately after return:
```
handle() returned code=503
is_running immediately after handle() returns: True
stop() actually completed by then: False
RACE CONFIRMED: handle() returned 503 claiming the bridge is stopped, but
is_running is still True -- the exact assertion test_bridge_handle_stops_if_disabled
makes would FAIL here.
```
This proves the race exists by construction, independent of whether any particular test run happens to hit it — the code makes no promise, so failure is a matter of when, not if, under contention.

**Whether it reproduces only under suite ordering:** attempted a live full-suite and partial-suite (88-file / 1,186-test collection-order prefix ending at `test_mobile_bridge.py`) re-reproduction of the audit's "failed identically in two independent full-suite runs" observation, on the pre-fix code (via `git stash` to temporarily revert the in-progress fix). **Both attempts were abandoned incomplete** — this environment's real-Tk-GUI test wall-clock cost made a full ~1,900-test run impractically slow within this session (progressed only ~19% of the 1,186-test prefix after several minutes of background execution). This is an environmental/time-budget limitation, not a finding that the race doesn't reproduce under ordering — the structural proof above already establishes the race is real and does not depend on empirically catching it in a specific suite run. Not counted as a substitute for the audit's own already-documented full-suite failure; treated as corroborating, not primary, evidence.

**Not modified:** the test file itself was not touched at any point.

## Phase 2 — Contract trace

- **What `handle()` promises when disabled:** "Security invariant: if settings say disabled we MUST NOT be running. If we somehow are, force-stop immediately before processing" (the code's own comment). The promise is immediate/synchronous by its own wording.
- **Stop function invoked:** `MobileBridge.stop()` — already bounds its own blocking: `srv.shutdown()` (blocks until the `serve_forever()` loop notices, default `poll_interval=0.5s`) plus `thread.join(timeout=0.25)`. Bounded, not unbounded.
- **Do callers depend on synchronous completion?** Yes — the regression test itself (checking `is_running` immediately after `handle()` returns) encodes exactly that expectation, matching the security-invariant comment.
- **Can waiting deadlock the GUI/event loop?** No. `handle()` is invoked exclusively from `BaseHTTPRequestHandler.do_GET/do_POST/do_PUT/do_PATCH/do_DELETE` inside the `Handler` class defined in `_start()` — these run on `ThreadingHTTPServer` per-request worker threads (via `ThreadingMixIn`), never on the Tk/GUI main thread. Grepped every call site of `.handle(` in `cache_vault/` — all five are inside that same `Handler` class. The GUI thread never calls `MobileBridge.handle()`.
- **Does another code path already demonstrate the intended synchronization pattern?** Yes — `MobileAccessController.disable()` (`cache_vault/core/mobile/mobile_access_controller.py:195`) calls `self._bridge.stop()` **directly and synchronously**, and is itself invoked directly from GUI Tk callbacks (`cache_vault/ui/settings_hub.py:779`, `cache_vault/ui/shell.py:4978`) with no reported freeze/deadlock issue. This is the exact same `stop()` call, made synchronously, from a *more* GUI-sensitive call site than `handle()`'s own HTTP-worker-thread context.
- **Security vs. correctness vs. test assumption:** the security requirement (disabled ⇒ not running) and the test assumption (checkable immediately, synchronously) are one and the same as written in the code's own comment — there is no separate, looser "eventually stops" requirement documented anywhere. The audit's diagnosis holds: this is a real defect, not a mismatched test expectation.
- **git history check:** no commit message anywhere in the repo's history mentions "force-stop" or explains why async dispatch was chosen for this specific path (`git log --all --grep="force-stop"` — no hits). No evidence this was a deliberate deadlock-avoidance design; it reads as an inconsistency against the pattern already established in `disable()`.

**Conclusion: audit's diagnosis confirmed correct.** Proceeded to Phase 3.

## Phase 3 — Minimal fix

Replaced the async dispatch with a direct synchronous call, matching the already-established pattern in `MobileAccessController.disable()`:

```diff
-        if not self.vault.settings.mobile_access_enabled:
-            if self.is_running:
-                import threading
-                threading.Thread(
-                    target=self.stop,
-                    name="mobile-bridge-force-stop",
-                    daemon=True,
-                ).start()
+        if not self.vault.settings.mobile_access_enabled:
+            if self.is_running:
+                self.stop()
```
(plus an explanatory comment recorded above the block — see the actual diff below).

**Timeout/deadlock analysis:** `stop()`'s own blocking is already bounded (`srv.shutdown()` — waits for the `serve_forever` loop's next `poll_interval` check, default 0.5s worst case; `thread.join(timeout=0.25)` — explicitly bounded). No new synchronization primitive was introduced; none was needed. No unbounded GUI-thread wait was introduced because this code path never runs on the GUI thread in the first place (see Phase 2). No deadlock risk: `stop()`'s `srv.shutdown()` is called from a request-handler worker thread, distinct from `self._thread` (the thread actually running `serve_forever()`) — exactly the "different thread" precondition Python's `socketserver.BaseServer.shutdown()` requires.

**Not done:** no MobileBridge redesign, no LAN-IP change, no E4b work, no pairing/token changes, no Android changes, no unrelated threading refactor, no public-behavior change beyond removing the race, no weakening of the regression test.

## Phase 4 — Regression proof

| Check | Command | Result |
|---|---|---|
| Focused test | `pytest tests/test_mobile_bridge.py::test_bridge_handle_stops_if_disabled -v` | **PASS** (0.66s — now takes measurably longer than the pre-fix 0.14s, consistent with `stop()` now actually running to completion synchronously instead of racing) |
| Full MobileBridge suite | `pytest tests/test_mobile_bridge.py` | **PASS** (all 64 tests) |
| Full mobile-lifecycle regression scope | `pytest tests/test_connection_doctor.py tests/test_d3_mobile_model.py tests/test_mobile_access_screen.py tests/test_mobile_bridge.py tests/test_mobile_connection_lifecycle.py tests/test_mobile_discovery.py tests/test_mobile_image_inbox.py tests/test_mobile_inbox.py tests/test_mobile_pairing.py tests/test_mobile_send_ignores_capture_pause.py tests/unit/test_pairing_offer.py` | **PASS** — 149 passed in 32.09s (re-confirmed with exit code 0 after restoring the fix from a temporary stash used for Phase 1's before-state reproduction) |
| Full-suite / order-pollution scenario | Attempted (see Phase 1) | **Incomplete/inconclusive** — abandoned after ~19% of a 1,186-test collection-order prefix due to this environment's real-Tk-GUI-test wall-clock cost; not a negative result, an unfinished one. Structural proof (Phase 1) is treated as the authoritative evidence of the race instead. |
| `app.py --selftest` | `python app.py --selftest` | **PASS** — "selftest OK — core capture/classify/sensitive/image/mobile pipeline works" |
| Syntax/import validation | `python -m py_compile ...`, `python -c "import cache_vault.core.mobile.bridge"`, `python -m compileall -q cache_vault` | **PASS**, all three |
| `git diff --check` | — | Clean |

**No unrelated environmental failures encountered** in any completed run (the incomplete full-suite/prefix attempts produced zero failures in their partial progress — they were stopped for time, not because anything failed).

## Phase 5 — Candidate

- **Baseline:** `6ec7bffbf487f3a07248e56fed9a19f5dade777f`
- **Candidate:** `d554fee4c57e7dc2f0ddcb909634fa9dfe9614c4` on branch `fix/gate-b-mobile-bridge-force-stop`
- **Production files changed:** `cache_vault/core/mobile/bridge.py` only (1 file, 15 insertions, 6 deletions)
- **Tests changed/added:** none — the existing test was neither modified nor weakened
- **Failing-before evidence:** structural/deterministic proof (Phase 1); test passes in isolation but the race is provable by construction
- **Passing-after evidence:** focused test + full 64-test MobileBridge suite + full 149-test mobile-lifecycle regression, all pass
- **Full-suite/order result:** attempted, incomplete due to environment wall-clock cost — see Phase 1/4 disclosure above
- **Timeout/deadlock risk introduced:** none — `stop()`'s blocking was already bounded before this change; this change only removed the unawaited-thread indirection, it did not add any new wait
- **Diff summary:** see Phase 3 above; full diff is in the commit `d554fee`

**Not fast-forwarded to `master`. Not pushed.**

## Production source confirmation

`git diff --stat` for this gate touches exactly one file: `cache_vault/core/mobile/bridge.py`. No Android source, no other Python source, no test files, no E4b work, no LAN-IP changes, no pairing/token changes.
