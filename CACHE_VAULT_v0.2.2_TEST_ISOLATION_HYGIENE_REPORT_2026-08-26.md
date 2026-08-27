# Cache Vault v0.2.2 — Test Isolation Hygiene / Env Leak Fix Report

**This is a test-hygiene gate only.** No build, rebuild, official artifact, tag, push, publish,
deploy, GitHub mutation, signing, human walkthrough, packaged launch, or windowed launch occurred.

---

## 1. Worktree path
`C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation`

## 2. Branch and HEAD before changes
```text
Branch: fix/v0.2.2-profile-isolation
HEAD:   ef4bfd70f95b64cc9d5086e3842b5d528e832d68
```
Preflight confirmed: no CacheVault process running; only the three pre-existing scratch profile
directories untracked (unchanged, not touched); real vault baseline `cache_vault.db` mtime
`2026-08-26 17:17:59`, receipt count `385,663` — reconfirmed unchanged at the end of this pass.

## 3. Failure reproduced
```text
pytest tests/test_profile_dir_flag.py tests/test_profile_isolation.py -q
→ 5 failed, 14 passed (before the fix)
```
Reproduced exactly as reported in the prior gate.

## 4. Root cause
Three test functions in `tests/test_profile_dir_flag.py` call `app._apply_and_verify_profile_dir()`
directly — real product code that performs real `os.environ["LOCALAPPDATA"] = ...` (and
`USERPROFILE`/`TEMP`/`TMP`) assignments, with no `monkeypatch` wrapper around the call:

- `test_apply_profile_dir_redirects_all_profile_scoped_paths`
- `test_apply_profile_dir_creates_directory_if_missing`
- `test_apply_profile_dir_fails_closed_when_verification_fails`

None of these reverted the four environment variables after the test function returned, so
whichever ran last left `LOCALAPPDATA`/`USERPROFILE`/`TEMP`/`TMP` pointed at that test's own
`tmp_path`-derived isolated directory for the rest of the pytest process — corrupting
`tests/test_profile_isolation.py`'s assumption (baked in at `tests/conftest.py`/`tests/sandbox.py`
bootstrap time) that those four variables still point at the session sandbox.

**Confirmed test-only contamination, not product behavior:** each file passes 100% in isolation;
the failure only appears when both run in the same pytest process. `app._apply_and_verify_profile_dir()`
itself behaves exactly as designed (it's supposed to mutate the environment — that's the whole
point of `--profile-dir`); the bug is that these three *tests* call it without protecting the
ambient environment the way every other test in this codebase already does.

## 5. Files changed
```text
 tests/test_profile_dir_flag.py | 51 ++++++++++++++++++++++++++++++++++++++-
 1 file changed, 50 insertions(+), 1 deletion(-)
```
**Test code only. No product source file was changed.**

## 6. Fix applied
Added a small helper, `_protect_profile_env(monkeypatch)`, and called it at the top of each of the
three affected tests:
```python
_PROFILE_ENV_KEYS = ("LOCALAPPDATA", "USERPROFILE", "TEMP", "TMP")

def _protect_profile_env(monkeypatch):
    for key in _PROFILE_ENV_KEYS:
        monkeypatch.setenv(key, os.environ[key])
```
This pre-registers each key with `monkeypatch` at its *current* (sandboxed) value. `monkeypatch`'s
own automatic teardown then restores that recorded value when the test ends — regardless of what
`_apply_and_verify_profile_dir()` (or anything else during the test) subsequently writes to those
keys directly. This is the standard, idiomatic pytest pattern for protecting ambient state that
product code mutates without going through `monkeypatch` itself, and matches the safety spirit
already used elsewhere in this codebase (`tests/sandbox.py`'s own careful save/restore of the real
pre-redirect environment; `test_selftest_profile_containment.py`'s use of `subprocess.run(env=...)`
to avoid touching the parent process's environment at all).

Also added one new regression test,
`test_apply_profile_dir_does_not_leak_env_to_later_tests`, which calls
`_apply_and_verify_profile_dir()`, confirms it really did mutate the environment (so the guard
isn't vacuous), and asserts the pre-call values captured by `_protect_profile_env` match the
sandbox's own recorded defaults — directly proving the fix captures the right values to restore to.

Product code (`app.py`, `cache_vault/core/single_instance.py`, etc.) was **not** touched — the leak
was entirely in test code, and the fix stayed there, per the gate's scope.

## 7. Validation commands and results

```text
py_compile tests/test_profile_dir_flag.py                                    → SYNTAX OK

pytest tests/test_profile_dir_flag.py tests/test_profile_isolation.py -q     → 19 passed
  (the exact combination that failed before the fix)

pytest tests/test_single_instance.py tests/test_profile_dir_flag.py \
       tests/test_profile_isolation.py tests/test_selftest_profile_containment.py
                                                                                → 44 passed

pytest tests/test_build_meta.py tests/test_module_registry.py \
       tests/test_single_instance.py tests/test_profile_dir_flag.py \
       tests/test_profile_isolation.py tests/test_selftest_profile_containment.py
                                                                                → 70 passed in 7.85s
  (every focused suite touched by this whole v0.2.2 effort, combined in one process)
```
Full repository suite: **not run**, per instruction ("do not run full suite unless clearly safe and
bounded" — that remains the Focused Regression gate's job). No windowed or packaged app launch
occurred at any point. Real vault reconfirmed unchanged (`cache_vault.db` mtime and receipt count
identical to the baseline recorded at the start of this pass).

## 8. Confirmation: product source was not changed
Confirmed. `git diff --stat` shows exactly one file touched: `tests/test_profile_dir_flag.py`.
No file under `cache_vault/`, `app.py`, or `packaging/` was modified.

## 9. Confirmation: no build/release/tag/publish/push/GitHub/signing/windowed launch occurred
Confirmed. Only test-file edits and `pytest`/`py_compile` invocations occurred in this pass.

## Final classification

```text
A — TEST HYGIENE PASS / READY FOR RELEASE-CANDIDATE BUILD GATE
```

The specific combination that failed now passes, the fix is proven not to be vacuous by a dedicated
regression test, and every focused suite touched across this whole v0.2.2 effort (70 tests) now
passes together in a single process — removing the concern that a real full-suite run would hit
this same contamination. The Focused Regression / Release Proof gate can now proceed without this
blocker.
