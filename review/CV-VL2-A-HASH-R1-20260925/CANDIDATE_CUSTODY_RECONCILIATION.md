# CV-VL2-A-HASH-R1 — Candidate Custody Reconciliation

**Date:** 2026-09-25

**Mode:** Read-only candidate inspection; this report is the sole file created by this reconciliation.

## Disposition

```ini
CV_VL2_A_CUSTODY = LEGACY_HASH_UNREPRODUCIBLE
PHYSICAL_GATE_EXPECTED_SOURCE_ID = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
LEGACY_RECORDED_SHA256 = ffa3db0e015e4129d3a6dda4dbb29ad979d19697faac0bd6dd0d925854b300d2
LEGACY_RECORDED_SHA256_STATUS = HISTORICAL_ONLY; ORIGINAL_PROCEDURE_UNRECOVERABLE
REPRODUCIBLE_PRIOR_AUDIT_SHA256 = bdc2e0e438ac17bc04888f5d295fe80b6d4ac07f8fb01179614cf3619603aa55
CANONICAL_FILE_COUNT = 13
CANONICAL_FILE_LIST_SHA256 = 60ecdd28a870bbc72c36061b6063f49c665ca954973b4936905ebb1fcdc264e3
PACKAGE_CUSTODY = MATCH
SOURCE_CHANGED = NO
TESTS_RUN = NO
COMMIT = NO
PUSH = NO
```

The current working-tree candidate has a reproducible canonical identity and internally consistent Git state. The earlier `ffa3…` digest cannot be reproduced or tied to an earlier per-file ledger. Therefore the evidence does **not** prove that all candidate bytes are unchanged since the original freeze. The canonical hash above is the source identity to use for any subsequent physical gate; retain `ffa3…` as historical evidence only.

## Aggregate procedure reconstruction

### Original recorded digest: `ffa3…`

The preserved records provide the digest, the claim that it covered 13 files, and the expected temporary package digest. They do not preserve the exact original path list, a per-file raw-hash ledger, a hashing script/command, or the byte serialization. Consequently, the original procedure cannot be established for any of the requested dimensions:

| Procedure detail | Original `ffa3…` evidence |
|---|---|
| File selection and exact 13 paths | Not preserved as part of the original hash record; the current/audit manifest below cannot prove which paths were originally hashed. |
| Path separators, case normalization, and ordering | Unknown. |
| Untracked-file inclusion | Unknown. |
| Raw bytes versus decoded text | Unknown. |
| CRLF/LF normalization and BOM handling | Unknown. |
| Whether paths were included in the aggregate | Unknown. |
| Record separators and terminal newline behavior | Unknown. |
| File-size/other metadata inclusion | Unknown. |
| SHA-256 output casing/representation | The saved digest is lowercase hexadecimal; the procedure’s intermediate representation is unknown. |

No undocumented steps have been inferred. No old raw per-file SHA-256 values were recoverable, so every ledger row is `OLD_UNKNOWN`.

### Prior audit recomputation: `bdc2…`

The prior audit report documents this construction, and rerunning it over the current 13-file manifest and current raw bytes reproduces `bdc2e0e438ac17bc04888f5d295fe80b6d4ac07f8fb01179614cf3619603aa55`:

```text
SHA256(
  UTF8("BASE=3af328424c39d97d4af54156672a2e4b2d2b8c43\n") ||
  for each candidate path in ascending ordinal order:
    UTF8(path with '/' separators) || 0x00 || UINT64_LE(raw byte length) || raw file bytes
)
```

The selected manifest is listed below. These ASCII repository-relative paths were bytewise sorted by their UTF-8 encoding. The procedure reads raw bytes; it does not decode text, normalize line endings, or remove a BOM. The path, NUL separator, and 8-byte little-endian length precede each file body. The base line ends in LF; there is no additional record terminator after a file body. The aggregate output is lowercase hexadecimal SHA-256. The prior audit says it hashed the listed 13 files, including the two then-untracked candidate files. This establishes how `bdc2…` was produced, but it does not establish how `ffa3…` was produced.

## Per-file custody ledger

Current hashes below are SHA-256 over each file’s raw bytes. `OLD_RAW_SHA256_IF_RECOVERABLE` is unknown for all files because no original per-file ledger was preserved; therefore the comparison status is `OLD_UNKNOWN`, not a claim of a match.

| FILE (repository-relative) | TRACKED / UNTRACKED | SIZE_BYTES | CURRENT_RAW_SHA256 | OLD_RAW_SHA256_IF_RECOVERABLE | MATCH / MISMATCH / OLD_UNKNOWN |
|---|---:|---:|---|---|---|
| `cache_vault/core/mobile/bridge.py` | TRACKED | 31829 | `1b8639aea1d8448a203cbb0c7b5d54526606fd1dc04021292a957d32681c3fe9` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/core/settings.py` | TRACKED | 11680 | `15ccbe2c4ad817d20bad973154cd85a85040fdcd227ea8455e1fe3c0fba7208b` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/core/vault_lock.py` | TRACKED | 8289 | `e8bda65ff1878aea4a7442b23bf391a10b367a2f9e0365eae9c937df2f56a443` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/modules/registry.py` | TRACKED | 13497 | `21f3c13cc2321c364d68d36a7dfa8422240e1ca3138cfea7f6ead019a747d0e8` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/ui/dialogs.py` | TRACKED | 71405 | `2e623f7b952a33e9a55e8fd92119d6a394b98ef72248ba1cef3aeac7253e44c7` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/ui/shell.py` | TRACKED | 281431 | `ff0d91962ca65d2eba1eab4fa75741e8f2dc314aa62aacc07bcad4ae8712a113` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/ui/vault_lock.py` | TRACKED | 14377 | `2a1f8a6a11d8f08551ea92b1d107b2b7474f6c933ad4a82657b1fa9f6264931d` | UNKNOWN | OLD_UNKNOWN |
| `cache_vault/ui/windows_session_lock.py` | UNTRACKED | 3758 | `28374b25cf34cf918cdd84a4be90471f104f2a008d85c647e28a4b113d77c990` | UNKNOWN | OLD_UNKNOWN |
| `review/CV-VAULT-LOCK-2-20260924/RECONCILIATION.md` | UNTRACKED | 9159 | `6d9b2d31849aa0e06ca2ad4909d36d433cb5638dbae16c885125a8a88e73d230` | UNKNOWN | OLD_UNKNOWN |
| `tests/test_command_center_app.py` | TRACKED | 18709 | `aa2bbe8c7f83959de0263bdab42ee40d370a50394f3792617319e157594f77c3` | UNKNOWN | OLD_UNKNOWN |
| `tests/test_mobile_bridge.py` | TRACKED | 41453 | `2feef78b845cf59b58d8727d6695f879deb761c63f91c5a4663272aa8407676c` | UNKNOWN | OLD_UNKNOWN |
| `tests/test_vault_lock.py` | TRACKED | 7079 | `5717ca269e9676a542d7c5175ae183a76a52483cb706ecbc489141fe3aebbabd` | UNKNOWN | OLD_UNKNOWN |
| `tests/test_vault_lock_ui.py` | TRACKED | 15015 | `b7fff11c157c06ffa948a131dba8968b6a7f37c70f12b228142dd2998940f33e` | UNKNOWN | OLD_UNKNOWN |

## Canonical identity algorithm

The fixed candidate manifest is the 13 paths in the ledger. To calculate its canonical identity:

1. Represent each repository-relative path with `/` separators; do not case-fold.
2. Sort paths by ordinal bytewise order of their UTF-8 encodings.
3. For each path, read the exact raw file bytes and compute lowercase hexadecimal SHA-256.
4. Append one UTF-8 record per file to a byte stream: `<relative-path>\t<raw-file-sha256>\n`.
5. SHA-256 the concatenated record stream; use lowercase hexadecimal as the canonical candidate identity.
6. For `CANONICAL_FILE_LIST_SHA256`, hash the UTF-8 sorted path list with each path followed by LF, including one final LF. This file-list digest covers paths only, not per-file digests.

This algorithm uses no timestamps, absolute paths, environment metadata, text decoding, line-ending normalization, or BOM handling. Results:

```text
CANONICAL_CANDIDATE_SHA256 = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
CANONICAL_FILE_COUNT = 13
CANONICAL_FILE_LIST_SHA256 = 60ecdd28a870bbc72c36061b6063f49c665ca954973b4936905ebb1fcdc264e3
```

## Git state at reconciliation

```text
HEAD   = 3af328424c39d97d4af54156672a2e4b2d2b8c43
PARENT = af1869d6bac2a0f3184571819fed7e1eb57f9792
BRANCH = cv-vault-lock-2
```

`HEAD` is the base commit; the candidate is uncommitted.

`git status --short` before this report was created:

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
```

- `git diff --check`: PASS (exit 0; no output).
- Staged diff: empty; no staged paths or stat.
- Tracked unstaged diff: 11 files, 601 insertions, 57 deletions. The modified paths are the 11 `M` entries above.
- Untracked candidate files: `cache_vault/ui/windows_session_lock.py` and `review/CV-VAULT-LOCK-2-20260924/RECONCILIATION.md`.
- Other pre-existing untracked evidence: `review/CV-DT1A-20260925/TRUST_BOUNDARY_AUDIT.md`.
- Android diff (`git diff --name-status HEAD -- android`): empty.
- This reconciliation report is newly created and is outside the 13-file candidate manifest. It is the only file written during this task.

## Temporary package custody

The existing temporary package was checked without rebuilding it:

```text
EXPECTED_OLD_PACKAGE_SHA256 = 6e18b55c62e3abe6f860e7bfe08b0f0fa8df8acc6fc32d97b168e45b2aeecf8e
FOUND = C:\Users\KickA\AppData\Local\Temp\cv-vl2-r1-frozen-candidate-85a4d15739694c609adce26bbc57ebac\dist\CacheVault.exe
SIZE_BYTES = 43642564
COMPUTED_RAW_SHA256 = 6e18b55c62e3abe6f860e7bfe08b0f0fa8df8acc6fc32d97b168e45b2aeecf8e
PACKAGE_CUSTODY = MATCH
REBUILT = NO
```

Two other existing `CacheVault.exe` files under `cv-vl2*` temporary directories did not match the expected digest; they are not substituted for the exact matching artifact.

## Discrepancy classification

**F. ORIGINAL_ALGORITHM_UNRECOVERABLE**

The `bdc2…` procedure is reproducible from the prior audit record and current bytes. The `ffa3…` procedure and old per-file hashes are absent from preserved evidence. As a result, available evidence cannot distinguish an original serialization difference from a different file set or bytes at the time of the first hash. Classifying A–E would claim facts that the evidence does not establish.

```ini
CV_VL2_A_CUSTODY = LEGACY_HASH_UNREPRODUCIBLE
PHYSICAL_GATE_EXPECTED_SOURCE_ID = 2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877
LEGACY_RECORDED_SHA256 = ffa3db0e015e4129d3a6dda4dbb29ad979d19697faac0bd6dd0d925854b300d2
SOURCE_CHANGED = NO
COMMIT = NO
PUSH = NO
```
