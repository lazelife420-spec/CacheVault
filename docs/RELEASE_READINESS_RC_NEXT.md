# Release Readiness — next RC candidate

**Audit only.** No build, tag, release, or package publishing was performed. Existing
`dist/release/v0.1.3-rc5/` proof artifacts were not mutated.

## Summary

`master` now contains two mobile lanes (PR #11, PR #12) that landed **after** the last
v0.1.3-rc5 proof. The source version string is still `0.1.3-rc5`, so the next package
must **not** reuse the `rc5` name — it would be a stale label hiding newer code. The next
candidate should be **`v0.1.3-rc6`**.

## Phase A — version truth

| Fact | Value |
|------|-------|
| `master` commit | `d2bcb3aa99d0398612804115e9ce8789be877466` |
| `cache_vault.__version__` | `0.1.3-rc5` |
| `pyproject.toml` version | `0.1.3-rc5` |
| Working tree | clean |
| Last rc5 source commit | `66cf359` (per `docs/releases/v0.1.3-rc5.md` / `rc_gate.py`) |

### New on master since the rc5 artifact

- **PR #11** (`1808eb6`) — mobile LAN auto-discovery fix (mDNS service-type ≤15 bytes +
  reachable-IP advertise) and sensitive **warn-before-send** on the Android Share Sheet.
- **PR #12** (`f3e09a8`) — mobile **image** (`image/*`) Share Sheet send into the desktop
  vault (binary asset + receipts).

The shipped rc5 artifact was built from `66cf359` (discovery still broken, no
warn-before-send, no image send). **master is materially ahead of rc5.**

**Recommendation:** keep rc5 name — **NO**. Bump to rc6 before any package lane — **YES**.

## Phase B — proof gate (green)

| Check | Result |
|-------|--------|
| `pytest tests/` | **438 tests, no failures** (one run showed 1 non-deterministic environment skip) |
| `app.py --selftest` | **PASS** |
| Android `testDebugUnitTest` | **BUILD SUCCESSFUL** |

## Phase C — build / toolchain / packaging audit

| Item | State |
|------|-------|
| `packaging/build_exe.ps1` | present |
| `packaging/package_release.ps1` | present |
| `android/gradlew.bat` + Android SDK/Gradle | present (image lane built debug APK this session) |
| `tools/verify_exe_metadata.py` | present |
| `tools/verify_release_artifact.py` | present |
| `scripts/rc_gate.py` | present, **hardcoded `TAG="v0.1.3-rc5"`, `SOURCE_COMMIT="66cf359"`** |
| `packaging/RELEASE_NOTES-v0.1.3-rc5.md` | present, **stale** vs master (no discovery fix / warn / image content) |
| `packaging/RELEASE_NOTES-v0.1.3-rc6.md` | **absent — needed for rc6** |
| `docs/releases/v0.1.3-rc6.md` | **absent — needed for rc6** |
| `dist/release/v0.1.3-rc5/` | exists (prior proof) — **must not mutate** |

## Phase D — RC recommendation

To cut a clean **v0.1.3-rc6** candidate (when approved), the following changes are
required first (none done in this audit):

1. Bump `cache_vault.__version__` and `pyproject.toml` to `0.1.3-rc6` (this also flows
   into `verify_exe_metadata.py`, which gates on `__version__`).
2. Add `packaging/RELEASE_NOTES-v0.1.3-rc6.md` and `docs/releases/v0.1.3-rc6.md`
   (rc5 scope **plus** discovery fix, warn-before-send, image share).
3. Update `scripts/rc_gate.py` `TAG`/`SOURCE_COMMIT` to rc6 / current master (it writes to
   a tag-scoped `dist/release/<tag>/`, so rc5 artifacts stay untouched).

### Manual phone proof required for rc6 (real device)

- Auto-discovery finds the PC (now fixed — must be re-proven)
- Manual Setup pairing + hot-reload (no desktop restart)
- Share Sheet **text/link** send → inbox + receipt
- Share Sheet **image** send → image asset + receipt
- **Sensitive warn-before-send** intercept + confirm
- Unauthenticated / bad-token send rejected
- Locked desktop surfaces do not leak received items

## Verdict

- **Release readiness accepted:** YES (code green; toolchain ready)
- **Version bump needed:** YES (`0.1.3-rc5` → `0.1.3-rc6`)
- **Recommended next RC:** `v0.1.3-rc6`
- **RC package lane ready:** YES — *after* the rc6 version bump + notes + `rc_gate.py`
  update above; **no artifacts built or published in this audit** (awaiting approval)

## Scope / safety

No tag · no release · no package publishing · no HyperSnatch · no Easy Tap · no arbitrary
non-image file Share Sheet send · no cloud claim · no encryption claim · RC artifacts
untouched.
