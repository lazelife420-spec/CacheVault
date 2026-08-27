# Cache Vault v0.2.2 — Version / Release-Candidate Identity Gate Report

**This is an identity/version gate only.** No build, rebuild, official artifact, release ZIP, tag,
push, publish, deploy, upload, GitHub mutation, signing, human walkthrough, packaged launch, or
windowed launch occurred in this pass.

---

## 1. Worktree path
`C:\Users\KickA\Desktop\CacheVault-v0.2.2-profile-isolation`

## 2. Branch and HEAD before changes
```text
Branch: fix/v0.2.2-profile-isolation
HEAD:   2ad36c5d4a05e8edb0afbcca7be5080509c33d97
```
Preflight confirmed all four expected commits present (`b232844`, `3c06c72`, `a01faa7`, `2ad36c5`),
no CacheVault process running, real vault baseline unchanged (`cache_vault.db` mtime
`2026-08-26 17:17:59`, receipt count `385,663`) — reconfirmed at the end of this pass, still
identical.

## 3. Files changed
```text
 CHANGELOG.md            | 50 ++++++++++++++++++++++++++++++++++++++++++++++++++
 README.md               |  2 +-
 RELEASE_NOTES.md        | 28 ++++++++++++++++++++++++++
 cache_vault/__init__.py |  4 ++--
 pyproject.toml          |  2 +-
 5 files changed, 82 insertions(+), 4 deletions(-)
```
The three pre-existing scratch profile directories from prior gates remain untracked, untouched,
not staged.

## 4. Version surfaces found

| Surface | Before | Notes |
|---|---|---|
| `pyproject.toml` | `version = "0.2.1"` | Package version, single source of truth alongside `__init__.py` |
| `cache_vault/__init__.py` | `__version__ = "0.2.1"`, `__release_label__ = "Public Release"` | Feeds PyInstaller's Windows `FileVersion`/`ProductVersion` via `build_meta.py`, and the in-app "Version X · label" string (`ui/module_registry` path) |
| `CHANGELOG.md` | Top entry `## Cache Vault v0.2.1` | House convention: version gets its own header, not left under `Unreleased` |
| `README.md` | `## Honest scope & limitations (current, v0.2.1)` | Cosmetic version label in a section heading |
| `RELEASE_NOTES.md` | `# Cache Vault v0.2.1 (READY FOR PUBLICATION — NOT YET PUBLISHED)` | Top-level release-status document |
| `packaging/cache_vault.spec`, `cache_vault/build_meta.py` | No literal version string — reads `__version__` at build/import time | Nothing to edit here; confirmed by reading both files |
| `tests/test_build_meta.py`, `tests/test_module_registry.py` | Assert `pyproject_version == __version__` and a format string using the live `__version__`/`__release_label__` | Relative assertions, not hardcoded — pass automatically once both surfaces are bumped together |
| Android (`build.gradle.kts` references, found only inside historical docs) | `versionName "0.2.1"` / `versionCode 8` | Independently versioned companion, per this project's own `CANONICAL_PROJECT_RECORD.md` ("Desktop and the Android companion are separate deliverables with separate release cadences") — **not touched**, per instruction |

## 5. Version surfaces updated

1. `pyproject.toml`: `version = "0.2.1"` → `"0.2.2"`.
2. `cache_vault/__init__.py`: `__version__ = "0.2.1"` → `"0.2.2"`; **also** `__release_label__ =
   "Public Release"` → `"Release Candidate"`. This second change wasn't explicitly named in the
   gate's surface list, but leaving it as "Public Release" would have made the app itself display
   a false claim ("Version 0.2.2 · Public Release") for a build that isn't released — directly
   contradicts the gate's own "preserve accurate claim" requirement, so it was corrected.
3. `CHANGELOG.md`: added a new `## Cache Vault v0.2.2 (release candidate — not yet built,
   packaged, or published)` section above the existing `## Cache Vault v0.2.1` entry (which is
   left untouched, as history). Covers, per the gate's required content list: `--profile-dir`
   support, profile-scoped mutex, fail-closed pre-capture verification, source-windowed proof
   passed, packaged proof passed, human walkthrough passed against the isolated packaged
   candidate, and explicit "not yet done" lines for official build/full regression/tag/publish.
4. `README.md`: `(current, v0.2.1)` → `(current, v0.2.2)`.
5. `RELEASE_NOTES.md`: added a new top section for v0.2.2 (candidate status, explicitly not
   built/published, names the proof-candidate hash and clarifies that hash predates this version
   bump so a fresh build is needed before any publish step), ahead of the existing v0.2.1 section
   (left untouched, as history of that earlier, now-superseded gate).

## 6. Remaining 0.2.1 references and classification

All remaining `0.2.1` references were re-grepped after the edits and classified:

- **`CHANGELOG.md`, `RELEASE_NOTES.md` (own history section)** — intentional, historical: the
  v0.2.1 entry describes what actually happened at that gate and must not be rewritten.
- **Every `CACHE_VAULT_*_2026-08-26.md`, `CACHE_VAULT_FINAL_RELEASE_*`, `CACHE_VAULT_RELEASE_
  CLOSURE_*`, `CACHE_VAULT_S23_*`, `CANONICAL_PROJECT_RECORD.md`, `docs/CACHE_VAULT_FREE_VS_
  FOUNDER.md`, and the two `*_SUMMARY.json` files** — historical/receipt records of past gates;
  correctly frozen at what was true when each was written; not touched.
- **Android version references** (`versionName "0.2.1"` / `versionCode 8`, found only inside those
  same historical docs, not as a live file this pass edited) — independently versioned companion,
  explicitly not tied to the desktop version per this project's own canonical record; not touched,
  per instruction.
- **No drift found** — nothing was left inconsistent by accident; every remaining `0.2.1` string
  is either genuinely historical or the (untouched, correctly independent) Android version.

## 7. Validation commands and results

- **Syntax:** `py_compile` on `cache_vault/__init__.py` — OK.
- **Version consistency:** loaded `pyproject.toml` via `tomllib` and imported `cache_vault`,
  asserted `pyproject_version == cache_vault.__version__` — both `0.2.2`, match confirmed
  programmatically, not just by inspection.
- **Focused version-identity tests:** `test_build_meta.py` + `test_module_registry.py` — 26 passed.
- **Focused profile-isolation tests** (each run in its own process): `test_single_instance.py` — 11
  passed; `test_profile_dir_flag.py` — 9 passed; `test_profile_isolation.py` — 9 passed;
  `test_selftest_profile_containment.py` — 14 passed. **43 passed total.**
- **Full suite:** not run in this gate, per instruction ("do not run full suite unless clearly safe
  and bounded" — that's the next gate's job, explicitly).
- **No windowed app launch occurred** at any point in this pass.

### One real finding surfaced by validation — not caused by this gate's changes, flagged for the next one

Running `test_profile_dir_flag.py` and `test_profile_isolation.py` **in the same pytest process**
(as opposed to separate invocations, which is how they were run in the prior patch gate and how
they're reported as passing above) produces **5 failures** in `test_profile_isolation.py`. Root
cause, confirmed by isolating it: `test_profile_dir_flag.py`'s
`test_apply_profile_dir_fails_closed_when_verification_fails` (and its sibling direct-call tests)
invoke `app._apply_and_verify_profile_dir()`, which does a real `os.environ[...] = ...` mutation —
not a `monkeypatch.setenv()` — so the mutation is never automatically reverted, leaking into
whatever test runs next in the same process. This is a **pre-existing bug in the previous gate's
test file**, not something introduced by this gate's version-surface edits, and not something I
fixed here — that's out of this gate's stated scope (version surfaces only). **This must be fixed
before the next "Focused Regression / Release Proof Gate" can be trusted**, since a real full-suite
run would hit exactly this same leak (both files sort alphabetically adjacent, `dir_flag` before
`isolation`).

## 8. Statement: no build/release/tag/publish/push/GitHub/signing/windowed launch occurred
Confirmed. Only five text files were edited (version/changelog/release-notes surfaces); no build
command, no `git tag`, no `git push`, no GitHub interaction, no signing, no packaged or windowed
app launch happened in this pass. Real vault (`cache_vault.db` mtime, receipt count) reconfirmed
unchanged at the very end.

## 9. Next required gate

Per the plan, in order:
1. Commit this identity gate (pending review).
2. `CACHE VAULT v0.2.2 — FOCUSED REGRESSION / RELEASE PROOF GATE` — **must first fix the
   cross-test-file environment leak identified in §7**, or scope the regression run to avoid
   combining those two files in one process, before any full-suite result from this codebase can
   be trusted.
3. `CACHE VAULT v0.2.2 — OFFICIAL ARTIFACT BUILD / NO PUBLICATION`
4. `CACHE VAULT v0.2.2 — RELEASE ROOM DECISION`

## Final classification

```text
B — VERSION IDENTITY PASS WITH BOUNDED DRIFT
```

The version-identity change itself is clean — no drift, no ambiguity, both surfaces programmatically
confirmed to match, all directly-relevant focused tests pass. The "bounded drift" qualifier is for
the test-isolation bug surfaced during validation (§7) — real, pre-existing, and outside this
gate's authorized scope to fix, but it must be resolved before the next regression gate, or that
gate's results won't be trustworthy either.
