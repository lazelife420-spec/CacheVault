# Cache Vault — Python CI Gate Update

Date: 2026-07-03
Branch: `ci/drop-python-311-required-pr-gate`
Base: `release/v0.1.4-public-distribution` @ `8bbdac9`
Type: **Single-file CI policy change.** No app, test, or release code touched.

## What changed

`.github/workflows/ci.yml`: Python 3.11 is removed from the default
push/PR matrix.

```yaml
matrix:
  python-version: ["3.12", "3.13"]
```

(previously `["3.11", "3.12", "3.13"]`). Every step is otherwise unchanged.
The default CI gate now runs and blocks on **3.12 and 3.13 only**. 3.11 is
not run automatically anywhere in this workflow.

An earlier version of this change kept 3.11 in the matrix with
`continue-on-error: ${{ matrix.python-version == '3.11' }}`, which stopped
a failed 3.11 job from failing the workflow but did **not** stop it from
running, and it still occupied a pending PR check for up to 67 minutes.
That doesn't solve the actual problem, so the leg is removed instead of
softened.

## Why

This follows from `docs/CACHE_VAULT_PYTHON_CI_SUPPORT_POLICY_AUDIT_2026-07-03.md`,
which established:
- The only Python version that builds the shipped release EXE is **3.13**
  (`.github/workflows/release.yml`, unaffected by this change).
- 3.11 appeared nowhere except the CI test matrix — a source/dev
  compatibility check, not a shipping requirement.
- Neither `release/v0.1.4-public-distribution` nor `master` has any GitHub
  branch protection configured, so no "required checks" list needs to
  change to implement this.

That audit was written because 3.11 had already stalled once on PR #12.
Since then it repeated three more times, across two unrelated docs-only
PRs, with no code in common other than the CI workflow itself:

| PR | 3.11 result | 3.12 | 3.13 |
|----|-------------|------|------|
| #12, attempt 1 | stuck ~22min → cancelled | pass | pass |
| #12, attempt 2 | stuck ~21min → cancelled | pass (1m59s) | pass (2m9s) |
| #12, attempt 3 | stuck ~28min → cancelled | pass (2m5s) | pass (2m7s) |
| #13 | **passed, but took 1h 7m 12s** | pass (1m54s) | pass (2m26s) |

The PR #13 result is the reason `continue-on-error` isn't enough: 3.11
didn't fail there, it **passed** — but only after running roughly 30x
longer than 3.12/3.13. A non-blocking-on-failure job still ran, still sat
pending, and still tied up that PR's checks for over an hour. The only way
to stop that is to not run it on every push/PR at all.

## Why removal instead of continue-on-error or manual-only

- `continue-on-error` keeps the job in the automatic matrix, so it doesn't
  fix the duration problem demonstrated by PR #13 — this doc originally
  proposed it and is corrected here.
- Removing the entry from `ci.yml`'s matrix is the smallest change that
  actually stops 3.11 from running automatically: one line edited, no new
  workflow file.
- Optional 3.11 compatibility testing (manual/`workflow_dispatch`, or a
  separate lane) is deferred to a later, explicitly separate change if
  ever wanted. It is not part of this PR.

## Scope

```
Allowed and touched:
  .github/workflows/ci.yml
  docs/CACHE_VAULT_PYTHON_CI_GATE_UPDATE_2026-07-03.md

Not touched:
  app code
  tests
  release.yml (already 3.13-only; not affected by this change)
  proof/public/release notes
  generated artifacts
```

## Follow-up

PR #12 and PR #13 remain parked. Once this gate lands, they should be
rerun or rebased so their checks reflect the corrected matrix (3.12/3.13
only) before being reconsidered for merge.
