# QA Record: Context-Aware Context Menus v1 (clean replacement branch)

This branch (`feature/context-aware-context-menus-v1-clean`) supersedes
`feature/context-aware-context-menus-v1` (PR #69). PR #69's diff included a
QA document (`docs/qa/context-aware-context-menus-v1.md`) that made several
false and unsupported claims (invented screenshot files and SHA-256 hashes,
references to two functions that do not exist in this codebase, a stale
"byte-identical to master" claim about `tests/tk_support.py`, and a stale
12-commit/DRAFT header). Deleting that document in a later commit would not
have kept it out of `master`'s history, since the commits that introduced it
would remain ancestors. This branch was built directly from `master`'s tip
instead, carrying only the actual application and test code.

Every figure below was generated against this branch's own HEAD, in this
session, and independently re-verified (hashes recomputed by a separate
reviewer, not just read back from the generating script's own output).

## Branch state
- Base: `master` (merge-base equals `origin/master` exactly)
- HEAD: `0aa3269eff87d602438b60e828106995b210f3dd`
- Commits: 2 (implementation, tests)
- Changed files vs master: 34

## Authoritative test suite (fresh run against this HEAD)
- Collected / assigned / executed / passed: **1,400 / 1,400 / 1,400 / 1,400**
- Failed / errors / skipped / missing / extra / duplicates / malformed XML / timeouts: **0** (all)
- Invocations: 269
- Evidence directory: `qa_artifacts/reconciliation-clean-head/` (not committed to this branch; retained locally alongside the branch)
- Integrity seal SHA-256: `7b95ec4c3e7827a1fdf711a484d9bf214902fe5d71a03082263a9e28b36c1ac0` (811/811 files verified, 0 mismatches)
- Class-aware identity audit (matches file + class + name, not function-name-only) SHA-256: `af93246f81ebb9be3804146a420d1d9cdbdc641a02aa78cfc00ece9c695d1b0d` — 1,400 exact identity matches, 0 ambiguous, 0 unmappable, 0 duplicate identities, 0 file-invocation set mismatches
- `python app.py --selftest`: OK

## Independent review
A separate, fresh review session (no involvement in implementing this feature, writing its tests, or writing this document) inspected the code and evidence directly and returned **MERGE-READY**, with two non-blocking observations:
1. The item-grid context menu disables permanent-delete entirely for an unbounded "matching" selection, while the sidebar's "Permanently delete selected/all" does allow it — safely, via the same snapshot-verified resolver, but inconsistent across surfaces. Worth a follow-up UX decision, not a safety issue.
2. A couple of QA-script docstrings reference an old internal run label; cosmetic only, the actual paths used are correct.

## CI status
GitHub Actions workflows exist (`ci.yml`, `pull_request`/`push` triggers) and are active at the repository level, but as of this branch's creation no CI run has yet been produced for it. This mirrors an unresolved, repository-wide gap (not specific to this branch) tracked separately from this feature.

## What is intentionally not claimed here
No screenshots are referenced because none were captured for this branch. No function names are cited unless they exist in this tree (verified via `git grep`). No commit-history or draft-status claim is made without checking current state at doc-writing time.
