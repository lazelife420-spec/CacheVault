# Cache Vault v0.2.2 — Profile-Isolation Patch Report

**This is engineering work, but not a release gate.** No release artifact was built, no tag was
created, no publish/deploy/upload/push/GitHub action occurred, and no normal windowed Cache Vault
launch happened at any point in this pass.

---

## 1. Patch worktree path
`C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation` — a fresh `git worktree`, distinct
from the diagnostic worktree (`CacheVault-isolation-diagnostic-ab0b9a0`), which was read only for
reference (its `--profile-probe` diagnostic informed this patch's design) and was not committed to,
not modified, and not deleted.

## 2. Branch and HEAD
```text
Branch: fix/v0.2.2-profile-isolation  (new, created this gate)
HEAD:   ab0b9a088a7e386e34536e023895b01ba8256be7  (same commit the diagnostic pass and the
                                                     incident/root-cause reports are anchored to)
```

## 3. Files changed
```text
 app.py                              |  92 ++++++++++++++++++++++++++++++--
 cache_vault/core/single_instance.py |  55 +++++++++++++++++--
 tests/test_single_instance.py       | 103 ++++++++++++++++++++++++++++++++++++
 tests/test_profile_dir_flag.py      | new file
```
Nothing else touched. All changes are uncommitted in this worktree, as instructed.

## 4. Exact behavior added

**`app.py`:**
- `--profile-dir <path>` (also accepts `--profile-dir=<path>`), parsed and applied at the very top
  of `main()` — before `--selftest`, before `Settings.load()`, before `single_instance.claim_or_exit()`,
  before any tray/mobile/capture/UI code.
- Missing a value after `--profile-dir` fails closed immediately (`SystemExit(2)`, clear stderr
  message) — never silently falls through to the real profile.
- `_apply_and_verify_profile_dir()` sets `LOCALAPPDATA`/`TEMP`/`TMP`/`USERPROFILE` to the resolved
  path, creates it if missing, then **re-derives** `default_settings_path()`, `default_db_path()`,
  and `default_receipts_path()` and asserts each one actually resolves inside the requested
  directory. Any mismatch — today, or from some future code change that adds a new profile-scoped
  path outside this mechanism — fails closed (`SystemExit(3)`, clear stderr message) before any
  storage/tray/mobile/capture code can run. This is the direct answer to the correction from the
  prior gate: isolation is verified, not just requested.
- `claim_or_exit()` is now called with the resolved `profile_dir` (or `None` for a normal launch).

**`cache_vault/core/single_instance.py`:**
- `_mutex_name(profile_dir)`: `profile_dir=None` returns the exact original fixed mutex name,
  unchanged — a normal/real launch's single-instance behavior is byte-for-byte identical to before.
  A truthy `profile_dir` returns a name derived from the resolved, lowercased path (SHA-256, first
  16 hex chars) — deterministic per path, distinct across different profiles, and structurally
  incapable of colliding with the real (unscoped) name.
- `claim_or_exit(profile_dir=None)`: uses the scoped name to `CreateMutexW`. Critically, when
  `profile_dir` is truthy, `_raise_existing_window()` is **never called**, even on a mutex
  collision — an isolated launch can no longer bring any window (real-profile or otherwise) to the
  foreground under any circumstance. It falls straight to the "already running" message box and
  exits, exactly like the pre-existing no-window-found path always has.

## 5. Startup-order safety explanation

```text
main()
 ├─ _resolve_profile_dir_arg()                  [pure parse, no side effects]
 ├─ if profile_dir: _apply_and_verify_profile_dir()   [sets env, VERIFIES, fails closed]
 ├─ if "--selftest": _run_contained_selftest()  [unchanged; its own containment still applies]
 ├─ Settings.load()                             [now reads the verified-isolated LOCALAPPDATA]
 ├─ single_instance.claim_or_exit(profile_dir)  [scoped mutex; never redirects if isolated]
 └─ ... tray / mobile / capture / UI construction, only reachable after all of the above
```
Every subsystem capable of writing to a real profile — settings, storage, mobile receipts, the
single-instance mutex — is now either verified-redirected or scope-isolated *before* the point
where tray, mobile-bridge, or capture logic can start. Nothing new was added after that point that
could bypass it.

## 6. Tests run and results

**Focused suites directly relevant to this patch (completed cleanly):**
```text
tests/test_single_instance.py + tests/test_profile_dir_flag.py   : 20 passed in 0.60s
tests/test_profile_isolation.py + tests/test_selftest_profile_containment.py : 23 passed in 4.22s
```
All 43 tests passed. The 8 new/modified single-instance tests specifically prove: default mutex
name is unchanged; isolated mutex names differ from default and from each other; isolated mutex
names are stable and case/path-form normalized for the same real directory;
`_raise_existing_window()` is never called when `profile_dir` is set (mocked, asserted via
`assert_not_called()`); the correct (scoped vs. fixed) name is actually passed to `CreateMutexW` in
each mode. The 9 new profile-dir-flag tests prove: both flag forms parse; a missing value fails
closed; applying the flag redirects all three profile-scoped paths; the directory is created if
missing; a simulated verification failure (monkeypatched escaped path) fails closed; the flag
composes safely with `--selftest` via subprocess and still never touches a sentinel standing in
for the real profile, even when the ambient `LOCALAPPDATA` is deliberately left pointed at that
sentinel; a bare `--profile-dir` with no value, run through the real entry point end-to-end via
subprocess, exits non-zero before reaching any further startup.

**Full repository test suite — attempted, inconclusive, not a pass or fail.** I ran the complete
suite as extra diligence beyond what this gate required. It did not finish: after ~55% (roughly
consistent with several hundred tests, many of them UI-heavy), the backgrounded run's output
stopped with no summary line at all — no "N passed", no "N failed". The wrapping `timeout 550`
almost certainly killed the underlying `pytest` process for running long (this repo's own docs
describe a suite in the high hundreds, and several test files are UI-construction-heavy); the
"exited with code 0" the harness reported belongs to the downstream `tail -80` in my pipeline,
which exits cleanly once its input closes regardless of why the upstream process was terminated —
not to pytest itself. **I am not claiming a full-suite pass.** The specifically relevant,
literally-required focused suites (item above) did complete cleanly and are the load-bearing
evidence for this gate. A genuine full-suite run, if wanted, should be a separate, longer-budgeted,
`run_in_background`-from-the-start pass — not re-attempted here to avoid burning more time on an
already-long gate.

## 7. Confirmation: no normal windowed launch occurred
Confirmed. Every test above either calls the new functions directly in-process, or runs
`python app.py --profile-dir ... [--selftest]` via subprocess — both headless. `CacheVault.exe`
(the packaged binary) was not launched, and no test constructs `CacheVaultApp()` or calls
`.mainloop()` (the repo's own `test_no_packaged_process_is_started_by_the_sandbox` guard already
enforces this for the sandbox/conftest layer; nothing added here does either). `tasklist` confirms
no `CacheVault.exe` process is running.

## 8. Confirmation: no real receipt contents opened/read/deleted
Confirmed. Re-hashed the three receipt files from the prior incident (metadata operation only) —
identical SHA-256 to every prior check in this whole thread. Contents were never opened.

## 9. Confirmation: no release build/tag/publish/push/GitHub action occurred
Confirmed. Only source edits (in this fresh worktree, uncommitted) and test runs occurred.

## 10. Remaining work before a walkthrough retry

- These changes are uncommitted in `fix/v0.2.2-profile-isolation` pending your review.
- A genuinely proven **windowed** isolation pass is still outstanding — everything validated here
  is headless (unit tests + `--selftest` composition). Before retrying the human walkthrough, a
  separate, explicitly-authorized gate should prove `CacheVault.exe --profile-dir <path>` (the
  packaged binary, windowed, no `--selftest`) actually opens against the isolated profile — this
  patch makes that provable (fail-closed verification, scoped mutex) but does not itself constitute
  that proof.
- The full test suite was not confirmed regression-clean end-to-end (see §6) — worth a proper,
  patient run before this is considered fully vetted.
- No version bump, changelog entry, or build was made — this stays a source-only patch candidate.

## Final classification

```text
A — PATCH IMPLEMENTED / HEADLESS PROOF PASS / READY FOR SEPARATE WINDOWED ISOLATION PROOF GATE
```

The minimum fix is implemented and its own headless test suite proves it does what it claims. The
next legitimate step is a separate, explicitly scoped gate to prove the windowed (packaged) launch
path — not a resumption of the v0.2.1 human walkthrough, and not this gate re-litigated.
