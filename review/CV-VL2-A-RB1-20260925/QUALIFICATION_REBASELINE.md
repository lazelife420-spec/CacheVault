# CV-VL2-A-RB1 — Current Candidate Qualification Re-baseline

**Date:** 2026-09-25

**Mode:** Qualification only. No source or test files were edited. This report is the sole repository file created for this re-baseline.

## Result

```ini
CV_VL2_A_REBASELINE = PASS
PHYSICAL_GATE_SOURCE_SHA256 = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
PHYSICAL_GATE_PACKAGE_SHA256 = 4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519
FULL_SUITE = PASS (exit 0; quiet output reached 100%)
COMPILE = PASS
DIFF_CHECK = PASS
ANDROID_PRESERVATION = PASS
PACKAGE_SELFTEST = PASS
COMMIT = NO
PUSH = NO
CLOSED_GREEN = NO
```

The legacy `ffa3…` aggregate remains unreproducible and is not used as an identity. The earlier package artifact remains available with its expected SHA, but it is not used as source-to-package proof. This re-baseline binds the physical gate to the current canonical source and the fresh package recorded here. Physical Windows and live Android qualification remain pending.

## Source custody

The canonical procedure and fixed 13-file list are defined in `review/CV-VL2-A-HASH-R1-20260925/CANDIDATE_CUSTODY_RECONCILIATION.md`. The identity was computed before qualification and again after the suite, compilation, package build, and package self-test.

```text
PRE_QUALIFICATION_SOURCE_SHA256  = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
POST_BUILD_SOURCE_SHA256         = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
CANONICAL_FILE_COUNT             = 13
CANONICAL_FILE_LIST_SHA256       = 60ecdd28a870bbc72c36061b6063f49c665ca954973b4936905ebb1fcdc264e3
SOURCE_ID_MATCH                  = YES
```

## Full controlled regression

The requested command completed successfully:

```text
COMMAND = python -m pytest -p no:xonsh -q
EXIT = 0
PROGRESS = 100%
FAILURES = 0 (pytest exit code was 0; no failure output)
PASSED/SKIPPED SPLIT = NOT RETAINED BY QUIET OUTPUT
```

That invocation did not emit a final pass/skip count. A separate collection-only run against the same unchanged candidate completed with exit 0 and counted **2,120 collected tests**:

```text
python -m pytest -p no:xonsh --collect-only -q
COLLECT_ONLY_EXIT = 0
COLLECTED = 2120
```

No pass or skip count has been reconstructed from progress output or older runs.

## Compile and static checks

```text
python -m compileall -q cache_vault  -> exit 0, PASS
git diff --check                    -> exit 0, PASS
```

## Android preservation

```text
git diff --name-only HEAD -- android                 = empty
git ls-files --others --exclude-standard -- android   = empty
ANDROID_SOURCE_CHANGED                               = NO
```

## Fresh temporary Windows package

The package was built from the verified candidate with a new temporary output and work directory. The pre-existing `6e18…` executable was not used as the new artifact or overwritten.

```text
COMMAND = python -m PyInstaller packaging/cache_vault.spec --noconfirm --clean --distpath <new-temp>\dist --workpath <new-temp>\work
BUILD_RESULT = PASS
BUILD_EXIT = 0
NEW_TEMP_PACKAGE_PATH = C:\Users\KickA\AppData\Local\Temp\cv-vl2-rb1-544f9443dbb741af9b46fa416d39c127\dist\CacheVault.exe
NEW_TEMP_PACKAGE_BYTES = 43642981
NEW_TEMP_PACKAGE_SHA256 = 4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519
```

The fresh executable was launched hidden and waited synchronously so the process exit status was captured:

```text
COMMAND = CacheVault.exe --profile-dir <new-temp>\disposable-profile --selftest
PROCESS_EXIT = 0
PROFILE_ISOLATION_PATH_CREATED = YES
TEMP_PACKAGE_SELFTEST = PASS
PACKAGE_SHA256_BEFORE_SELFTEST = 4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519
PACKAGE_SHA256_AFTER_SELFTEST  = 4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519
```

A first direct shell invocation of the windowed executable returned without a synchronous exit code and was not counted as proof. The waited invocation above is the qualifying self-test result.

The separately preserved prior executable was rehashed after the fresh build and still matches its historical artifact digest:

```text
OLD_PACKAGE_SHA256 = 6e18b55c62e3abe6f860e7bfe08b0f0fa8df8acc6fc32d97b168e45b2aeecf8e
OLD_PACKAGE_ARTIFACT_CONTINUITY = MATCH
```

## Git custody

```text
HEAD   = 3af328424c39d97d4af54156672a2e4b2d2b8c43
PARENT = af1869d6bac2a0f3184571819fed7e1eb57f9792
BRANCH = cv-vault-lock-2
```

`HEAD` is the base commit; the CV-VL2-A candidate remains uncommitted. `git status --short` immediately before writing this report was:

```text
 M cache_vault/core/mobile/bridge.py
 M cache_vault/core/settings.py
 M cache_vault/core/vault_lock.py
 M cache_vault/modules/registry.py
 M cache_vault/ui/dialogs.py
 M cache_vault/ui/shell.py
 M cache_vault/ui/vault_lock.py
 M tests/test_command_center_app.py
 M tests/test_mobile_bridge.py
 M tests/test_vault_lock.py
 M tests/test_vault_lock_ui.py
?? cache_vault/ui/windows_session_lock.py
?? review/CV-DT1A-20260925/
?? review/CV-VAULT-LOCK-2-20260924/
?? review/CV-VL2-A-HASH-R1-20260925/
```

The staged diff was empty. This report is a new untracked evidence file outside the canonical 13-file source manifest. No source or test files changed during this qualification, no production package was replaced, and no commit or push was made.

## Gate handoff

```ini
PHYSICAL_GATE_SOURCE_SHA256 = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
PHYSICAL_GATE_PACKAGE_SHA256 = 4031161561d68712973e1c888cd65ef7c3bf92e3d4f54d5293fbe6063ec10519
CV_VL2_A_REBASELINE = PASS
CLOSED_GREEN = NO
COMMIT = NO
PUSH = NO
```
