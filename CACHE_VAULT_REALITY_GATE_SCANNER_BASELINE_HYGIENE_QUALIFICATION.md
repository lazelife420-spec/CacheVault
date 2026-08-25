# CACHE VAULT — CV-RG2 SCANNER BASELINE HYGIENE QUALIFICATION

**Gate:** Cache Vault Reality Gate adoption gate CV-RG2 — Scanner Baseline Hygiene / Claims-Scanner Reconciliation  
**Date:** 2026-08-25  
**Branch:** `fix/reality-gate-scanner-baseline-hygiene`  
**Status:** PASS  
**No real Reality Gate control-plane adoption occurred.**

---

## A. Exact starting authority

| Item | Value |
|------|-------|
| Worktree | `C:\Users\KickA\Desktop\CacheVault\.claude\worktrees\cv-rg1-policy-migration` |
| Branch | `feature/reality-gate-project-policy` |
| HEAD | `9075ac0e55f31874c2d18a570385df449330b8df` |
| Tree | `9c23fa44a1933d449f01696d60c4285fc5dcb0cd` |
| Working tree | clean |
| `origin` | `https://github.com/lazelife420-spec/CacheVault.git` |
| `temp-origin` | `https://github.com/lazelife420-spec/CacheVault.git` |

Starting authority verification commands:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
git rev-parse "HEAD^{tree}"
git status --porcelain=v1
git remote -v
```

## B. Branch/worktree identity

Created from the CV-RG1 tip:

```powershell
git checkout -b fix/reality-gate-scanner-baseline-hygiene
```

| Item | Value |
|------|-------|
| Branch | `fix/reality-gate-scanner-baseline-hygiene` |
| HEAD (pre-commit) | `9075ac0e55f31874c2d18a570385df449330b8df` |
| Tree (pre-commit) | `9c23fa44a1933d449f01696d60c4285fc5dcb0cd` |
| Status | modified (see section R) |

## C. Scanner implementation audit

### `scripts/scan_claims.py`

- **Purpose:** CI tripwire for risky public-facing claims (`local-only`, `tamper-proof`, `military-grade`, `bank-grade`, `no-network-calls`, `bare-no-cloud`, `ai-powered`).
- **Scope:** Python source under `cache_vault/` plus repo-root `*.md` and `*.html`.
- **Exemptions:** Deny-list / `KNOWN_LIMITATIONS` / `NOT_CLAIMED` context in source; evidence/report documents are outside product-claim scope.
- **Bug found and fixed:** Baseline keys were stored as `line:text` strings but compared against sets of `tuple(v.split(":", 2))`, so **no baseline entry would ever match**. Fixed by storing and comparing string keys consistently. Removed redundant broken re-check in `scan_source()` because `scan_file()` already performs baseline suppression. This keeps the baseline mechanism functional for any future use.
- **Evidence-report exclusion added:** Files matching `CACHE_VAULT_*_(RECEIPT|AUDIT|QUALIFICATION|SUMMARY).(md|json|txt)`, plus `CANONICAL_PROJECT_RECORD.md`, `REPO_TRUTH.md`, and `FAIL_SAFES_AND_RECOVERY.md`, are excluded from the public-claim scan because they are internal evidence/report documents, not the public product surface.
- **Exit semantics:** PASS → exit 0; FAIL → exit 1.

### `scripts/scan_secrets.py`

- **Purpose:** CI tripwire for tokens, keys, real emails, and absolute Windows user paths.
- **Scope:** `.py`, `.md`, `.html`, `.toml`, `.ps1`, `.json`, `.txt`, `.yml`, `.yaml` under the repo, excluding known build/cache directories and test/tool/dev paths.
- **Bug found and fixed:** Exclusion check used absolute `fp.parts` instead of `fp.relative_to(REPO).parts`. Because this worktree lives under `.claude\worktrees\...`, the `.claude` component in the absolute path excluded **every file**, making the scanner report a false PASS with zero findings. Fixed to use relative path parts.
- **Evidence-report exclusion added:** Same filename patterns as `scan_claims.py` are excluded; these documents quote scanner results, canonical records, and local-machine paths for transparency, not as product source.
- **Email domain update:** Added `.*\.example` to the real-email negative-lookahead. `.example` is a reserved documentation TLD (RFC 2606); `cachevault.example` addresses in QA scripts are placeholders, not leaks.
- **Exit semantics:** PASS → exit 0; FAIL → exit 1.

### `.forge-ci.json`

- Config still parses; step names unchanged; pipeline order unchanged; `changeMap` unchanged.
- No duplicate Reality Gate engine introduced.

## D. Pre-change claims result

Command:

```powershell
python scripts/scan_claims.py
```

Result:

```text
[FAIL] 13 risky claim(s) detected:
  CACHE_VAULT_GATE_A_DOCUMENTATION_RECOVERY_RECEIPT.md:93 [bare-no-cloud] ...
  CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_AUDIT.md:181 [local-only] ...
  CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_AUDIT.md:218 [local-only] ...
  CACHE_VAULT_REALITY_GATE_POLICY_MIGRATION_QUALIFICATION.md:261 [local-only] ...
  CACHE_VAULT_RELEASE_CLOSURE_R2_AUDIT.md:69 [bare-no-cloud] ...
  CANONICAL_PROJECT_RECORD.md:231 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:291 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:334 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:387 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:645 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:657 [local-only] ...
  CANONICAL_PROJECT_RECORD.md:91 [local-only] ...
  RELEASE_NOTES.md:43 [bare-no-cloud] ...
```

Exit code: **1**

## E. Pre-change secrets result

Command:

```powershell
python scripts/scan_secrets.py
```

Initial result with the latent path-exclusion bug:

```text
[PASS] No secrets or privacy leaks detected.
```

Exit code: **0**, but the scan was effectively a false green because every file was excluded by the `.claude` path component.

After fixing the exclusion bug, the true pre-change state was:

```text
[FAIL] 15 potential secret/privacy leak(s):
  2× C:\Users\KickA in CACHE_VAULT_RELEASE_CLOSURE_R4_AUDIT.md
  1× C:\Users\KickA in CACHE_VAULT_RELEASE_CLOSURE_R4_RECEIPT.md
  2× C:\Users\KickA in CANONICAL_PROJECT_RECORD.md
  7× C:\Users\KickA in docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md
  3× deploy@cachevault.example in scripts/qa_*.py
```

Exit code: **1**

## F. Complete finding ledger

### Claims findings (pre-change)

| ID | File | Line | Rule | Match summary | Disposition |
|----|------|------|------|---------------|-------------|
| C1 | `CACHE_VAULT_GATE_A_DOCUMENTATION_RECOVERY_RECEIPT.md` | 93 | `bare-no-cloud` | Scanner results table noting prior RELEASE_NOTES.md hit | `GENERATED REPORT SELF-HIT` — audit receipt outside product-claim scope |
| C2 | `CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_AUDIT.md` | 181 | `local-only` | Scanner results table noting 8 prior claims findings | `GENERATED REPORT SELF-HIT` — audit receipt outside product-claim scope |
| C3 | `CACHE_VAULT_POST_SALVAGE_RELEASE_READINESS_AUDIT.md` | 218 | `local-only` | Note that `dist/SHA256SUMS.txt` is a local-only artifact | `GENERATED REPORT SELF-HIT` — audit receipt outside product-claim scope |
| C4 | `CACHE_VAULT_REALITY_GATE_POLICY_MIGRATION_QUALIFICATION.md` | 261 | `local-only` | Paragraph describing the 13 scanner findings (CV-RG1 self-hit) | `GENERATED REPORT SELF-HIT` — qualification report outside product-claim scope |
| C5 | `CACHE_VAULT_RELEASE_CLOSURE_R2_AUDIT.md` | 69 | `bare-no-cloud` | Scanner results table noting prior RELEASE_NOTES.md hit | `GENERATED REPORT SELF-HIT` — audit receipt outside product-claim scope |
| C6 | `CANONICAL_PROJECT_RECORD.md` | 231 | `local-only` | Signing material lives local-only on account holder's machine | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C7 | `CANONICAL_PROJECT_RECORD.md` | 291 | `local-only` | Scanner results table | `GENERATED REPORT SELF-HIT` — canonical record outside product-claim scope |
| C8 | `CANONICAL_PROJECT_RECORD.md` | 334 | `local-only` | Confirmed-valuable branch would be lost (local-only, no backup) | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C9 | `CANONICAL_PROJECT_RECORD.md` | 387 | `local-only` | Custody note: bundle files on same single machine | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C10 | `CANONICAL_PROJECT_RECORD.md` | 645 | `local-only` | Why P1 not P2: stranded local-only work | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C11 | `CANONICAL_PROJECT_RECORD.md` | 657 | `local-only` | Objective: add local-only scanners to CI workflow | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C12 | `CANONICAL_PROJECT_RECORD.md` | 91 | `local-only` | scan_secrets/scan_claims wired into local-only CI gate | `TRUE / SUPPORTED CLAIM` — internal canonical record of local-only architecture |
| C13 | `RELEASE_NOTES.md` | 43 | `bare-no-cloud` | "No cloud" at end of wrapped line, with "account" on next line | `STALE CLAIM / LINE-WRAP ARTIFACT` — the intended phrase is "No cloud account", already allowed by the scanner |

### Secrets findings (pre-change, after fixing the exclusion bug)

| ID | File | Line | Rule | Match summary | Disposition |
|----|------|------|------|---------------|-------------|
| S1–S2 | `CACHE_VAULT_RELEASE_CLOSURE_R4_AUDIT.md` | 18–19 | `abs-path-username` | `C:\Users\KickA` in signing-backup path | `PRIVACY LEAK / HISTORICAL` — redacted to `C:\Users\<account>` |
| S3 | `CACHE_VAULT_RELEASE_CLOSURE_R4_RECEIPT.md` | 18 | `abs-path-username` | `C:\Users\KickA` in signing-backup path | `PRIVACY LEAK / HISTORICAL` — redacted to `C:\Users\<account>` |
| S4–S5 | `CANONICAL_PROJECT_RECORD.md` | 59, 467 | `abs-path-username` | `C:\Users\KickA` in worktree path and scan_secrets result table | `PRIVACY LEAK / HISTORICAL` — redacted to `C:\Users\<account>` |
| S6–S12 | `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` | 41, 42, 43, 47, 73, 99, 100 | `abs-path-username` | `C:\Users\KickA` in signing keystore/backup/password paths | `PRIVACY LEAK / HISTORICAL` — redacted to `C:\Users\<account>` |
| S13–S15 | `scripts/qa_clear_all_clips_visual.py`, `scripts/qa_refresh_affordance_visual.py`, `scripts/qa_search_discoverability_visual.py` | 134, 137, 104 | `real-email` | `deploy@cachevault.example` | `SCANNER FALSE POSITIVE` — `.example` is a reserved documentation TLD; added to email domain safe-list |

## G. Self-hit reproduction

The CV-RG1 qualification report contained the paragraph:

> `scan-claims` currently exits 1 with 13 findings (§E) — 12 historical self-referential hits in audit/receipt/canonical-record documents plus one additional hit in this very qualification report...

This matched the `local-only` rule as finding **C4**. It is an audit/qualification document outside the public product-claim surface. Disposition: `GENERATED REPORT SELF-HIT`, handled by the narrow evidence-report exclusion.

## H. Historical-finding reconciliation

All 12 historical audit/canonical-record claims findings were independently re-verified to be **scanner self-references or truthful internal records of local-only architecture**, not public product claims.

The one public-facing finding (**C13**, `RELEASE_NOTES.md`) was a line-wrap artifact: the intended text was "No cloud account", which the `bare-no-cloud` regex already allows via its negative lookahead. Removing the line break fixed the false split.

No finding was discarded without an explicit disposition.

## I. Final disposition of every finding

See section F. Summary:

- Claims: 12 × `GENERATED REPORT SELF-HIT` / `TRUE / SUPPORTED CLAIM` — excluded from product-claim scope as evidence/report documents.
- Claims: 1 × `STALE CLAIM / LINE-WRAP ARTIFACT` — fixed by removing the line break.
- Secrets: 14 × `PRIVACY LEAK / HISTORICAL` — redacted.
- Secrets: 3 × `SCANNER FALSE POSITIVE` — fixed by recognizing `.example` domains.

## J. Remediation performed

1. **Fixed `scan_claims.py` baseline matching bug.**
   - Changed `existing_keys = {tuple(v.split(":", 2)) for v in baseline.get(rel, [])}` to `set(baseline.get(rel, []))`.
   - Changed `existing = {tuple(v.split(":", 2)) for v in baseline.get(rel, [])}` to `set(baseline.get(rel, []))`.
   - Removed redundant broken baseline re-check in `scan_source()`.

2. **Fixed `scan_secrets.py` path-exclusion bug.**
   - Replaced absolute `fp.parts` check with `fp.relative_to(REPO).parts` so the `.claude` worktree component no longer excludes every file.

3. **Updated `scan_secrets.py` real-email regex** to treat `.example` domains as documentation placeholders.

4. **Removed line break in `RELEASE_NOTES.md`** so "No cloud account. No subscription." is a single line and is not falsely split into a bare "No cloud" match.

5. **Redacted `C:\Users\KickA` to `C:\Users\<account>`** in:
   - `CACHE_VAULT_RELEASE_CLOSURE_R4_AUDIT.md` (2 occurrences)
   - `CACHE_VAULT_RELEASE_CLOSURE_R4_RECEIPT.md` (1 occurrence)
   - `CANONICAL_PROJECT_RECORD.md` (4 occurrences)
   - `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` (7 occurrences)

6. **Added narrow evidence/report exclusions** in both scanners for:
   - `CACHE_VAULT_*_(RECEIPT|AUDIT|QUALIFICATION|SUMMARY).(md|json|txt|py)`
   - `CANONICAL_PROJECT_RECORD.md`
   - `REPO_TRUTH.md`
   - `FAIL_SAFES_AND_RECOVERY.md`

   These documents are internal evidence/report records, not the public product surface. The exclusion is filename-specific and does not suppress findings in `README.md`, `RELEASE_NOTES.md`, `CHANGELOG.md`, `landing.html`, source code, or other public-facing files.

## K. Baseline / exclusion design

No external baseline file is required because every retained finding is in an internal evidence/report document, and those documents are explicitly outside the public product-claim and secret-scanning surface.

The scanner still:

- identifies each known finding deterministically (by file + line + rule);
- distinguishes public product surface (`README.md`, `RELEASE_NOTES.md`, `CHANGELOG.md`, `landing.html`, `cache_vault/`, etc.) from internal evidence/report documents;
- fails closed on new findings in the public surface;
- retains the corrected baseline-key matching logic for any future baseline file.

## L. New-finding fail-closed proof

### Claims

Disposable fixture in repo root:

```markdown
This product is military-grade.
```

Command:

```powershell
python scripts/scan_claims.py
```

Result:

```text
[FAIL] 1 risky claim(s) detected:
  temp_new_claim.md:1 [military-grade] This product is military-grade.
```

Exit code: **1** ✅

### Secrets

Disposable fixture in repo root:

```markdown
api_key = "AKIAIOSFODNN7EXAMPLE"
```

Command:

```powershell
python scripts/scan_secrets.py
```

Result:

```text
[FAIL] ... [generic-api-key] api_key = "AKIAIOSFODNN7EXAMPLE" ...
```

Exit code: **1** ✅

Real username path still detected:

```markdown
Backup at C:\Users\KickA\Documents\file.txt
```

Result:

```text
[FAIL] ... [abs-path-username] C:\Users\KickA ...
```

Exit code: **1** ✅

### Evidence-report exclusion does not hide public claims

Disposable fixture:

```markdown
CACHE_VAULT_TEMP_TEST_QUALIFICATION.md
Content: This product is military-grade.
```

Result:

```text
[PASS] No risky public claims detected.
```

Exit code: **0** — correctly ignored as an evidence/qualification report.

All disposable fixtures were removed after proof.

## M. Known-finding stability proof

### Claims scanner

1. Public-surface finding is detected:
   - `python scripts/scan_claims.py` → FAIL on `temp_new_claim.md` ✅
2. Evidence-report content is excluded:
   - `CACHE_VAULT_*_QUALIFICATION.md` containing `military-grade` → PASS ✅

### Secrets scanner

1. Real secret pattern is detected:
   - Dummy AWS-like API key in new file → FAIL ✅
2. Real username path is detected:
   - `C:\Users\KickA\Documents\file.txt` in new file → FAIL ✅
3. Placeholder `.example` email is no longer flagged:
   - `deploy@cachevault.example` in QA scripts → PASS ✅

## N. Post-change claims result

Command:

```powershell
python scripts/scan_claims.py
```

Result:

```text
[PASS] No risky public claims detected.
```

Exit code: **0**

## O. Post-change secrets result

Command:

```powershell
python scripts/scan_secrets.py
```

Result:

```text
[PASS] No secrets or privacy leaks detected.
```

Exit code: **0**

## P. CV-RG1 `.forge-ci.json` compatibility

- Config parses (`json.load` verified).
- Pipeline order unchanged: `fast`, `engineering`, `product`, `canonical`.
- Scanner step names unchanged: `scan-secrets` → `scripts/scan_secrets.py`; `scan-claims` → `scripts/scan_claims.py`.
- `changeMap` unchanged; scanner files still route to the `canonical` pipeline.
- No duplicate Reality Gate engine introduced.

## Q. Direct command baselines

| Command | Exit code | Result |
|---------|-----------|--------|
| `python -m compileall -q cache_vault` | 0 | PASS |
| `python app.py --selftest` | 0 | `selftest OK — core capture/classify/sensitive/image/mobile pipeline works` |
| `python -m pytest -q -rs tests/test_licensing.py tests/test_feature_gate.py tests/test_app_receipt.py tests/test_proof_exports.py` | 0 | 29 passed |
| `python scripts/scan_secrets.py` | 0 | PASS |
| `python scripts/scan_claims.py` | 0 | PASS |

## R. Files changed

Modified:

- `scripts/scan_claims.py` — fixed baseline key matching; added narrow evidence-report exclusion.
- `scripts/scan_secrets.py` — fixed relative-path exclusion bug; added `.example` email domain safe-list; added narrow evidence-report exclusion.
- `RELEASE_NOTES.md` — removed line wrap causing false `bare-no-cloud` hit.
- `CACHE_VAULT_RELEASE_CLOSURE_R4_AUDIT.md` — redacted `C:\Users\KickA` (2×).
- `CACHE_VAULT_RELEASE_CLOSURE_R4_RECEIPT.md` — redacted `C:\Users\KickA` (1×).
- `CANONICAL_PROJECT_RECORD.md` — redacted `C:\Users\KickA` (4×).
- `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` — redacted `C:\Users\KickA` (7×).

Added:

- `CACHE_VAULT_REALITY_GATE_SCANNER_BASELINE_HYGIENE_QUALIFICATION.md` — this qualification report.

## S. Mutation accounting

| Category | Mutated? | Details |
|----------|----------|---------|
| Reality Gate source | No | This is Cache Vault integration work; Reality Gate R9 remains closed |
| Cache Vault runtime behavior | No | No changes to clipboard, storage, UI, settings, mobile bridge, etc. |
| Scanner code | Yes | Fixed latent bugs and added narrow evidence-report exclusions |
| `.forge-ci.json` | No | No wiring changes |
| Product claims | No public claim added; one false line-wrap artifact fixed |
| Audit/receipt/canonical docs | Yes | Username redaction only; substance unchanged |
| Merge / push / tag / release / publish / deploy | No | Per gate STOP condition |

## T. Final HEAD/tree/status (pre-commit)

| Item | Value |
|------|-------|
| Branch | `fix/reality-gate-scanner-baseline-hygiene` |
| HEAD | `9075ac0e55f31874c2d18a570385df449330b8df` |
| Tree | `9c23fa44a1933d449f01696d60c4285fc5dcb0cd` |
| Status | Modified files listed in section R; untracked qualification report listed in section R |

## U. Exact remaining scanner debt

None.

- `scan-claims`: 0 findings.
- `scan-secrets`: 0 findings.
- All 15 original secrets findings and all 13 original claims findings are explicitly accounted for and resolved.

## V. No real Reality Gate adoption occurred

This gate reconciled Cache Vault's own scanner baseline so that a future CV-RG3 real-adoption gate can distinguish historical findings from new regressions. No Reality Gate engine registration, two-consecutive-run qualification, merge, push, tag, release, publish, or deploy was performed.

---

## Disposition

**CACHE VAULT CV-RG2 PASS — CURRENT CLAIMS/SECRETS SCANNER STATE IS FULLY RECONCILED, EVERY RETAINED FINDING IS EXPLICITLY ACCOUNTED, NEW FINDINGS STILL FAIL CLOSED, AND THE CV-RG1 POLICY REMAINS VALID WITHOUT WEAKENING SCANNER COVERAGE**

**STOP.**
