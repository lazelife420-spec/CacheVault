# Cache Vault — Repository Truth Audit

This document records the **verified state of the repository** so a stranger can
trust what is real, what is gated, what is local, and what is not yet built. It
is deliberately conservative: if something is not proven, it is labeled as such.

- **Audit date:** 2026-06-24
- **Audit basis:** direct reading of source + tests, the full passing test suite
  on this machine, and the packaging spec. Per-subsystem *runtime* proof is
  tracked separately (see `docs/RUNTIME_PROOF.md`, produced in a later pass).
- **Scope of this pass:** documentation/truth only. No product behavior was
  changed to produce this file.

---

## 1. Repository facts (verified)

| Item | Value |
|---|---|
| Product | Cache Vault™ |
| Version (`cache_vault/__init__.py` + `pyproject.toml`) | `0.1.3` |
| Release label | `Founder MVP` |
| Current branch | `feature/product-expansion-browser-clipper` |
| Default/origin HEAD | `master` |
| Remote | `github.com/Z3r0DayZion-install/CacheVault.git` |
| Latest commit | `ea344ab` — "test: make licensing import fail closed without cryptography" (2026-06-24) |
| Latest tag | `v0.1.3-founder-mvp.2` (also `.1`, `v0.1.3-founder-mvp`, `v0.1.2`, `v0.1.1`, `v0.1.0`) |
| Latest built artifact | `dist/CacheVault.exe` (~43 MB, built 2026-06-23) |

### Test state (this machine)
- **503 passed, 0 failed, 0 skipped** on Windows with a display + `pywin32` +
  `cryptography` installed.
- 58 test files. 15 `skip`/`skipif`/`xfail` markers exist; **all are
  conditional** (Tk UI unavailable / Windows-only clipboard / no-display
  pairing). None are unconditional skips, and none hide a product failure. On a
  headless CI box some of these would skip with an explicit reason.

### Dependency truth (important)
- `requirements.txt` lists the real runtime deps: `customtkinter`, `pystray`,
  `Pillow`, `pywin32` (Windows), `zeroconf`, and **`cryptography>=42.0.0`**.
- `cryptography` is **required**, not optional: it backs offline Ed25519 Founder
  license verification (`cache_vault/licensing.py`). Licensing **fails closed**
  if it is absent (verification returns `False`).
- The PyInstaller spec (`packaging/cache_vault.spec`) **does** bundle
  `cryptography` (+ `ed25519` and `serialization` submodules), so the shipped
  `.exe` can verify licenses.

**Phase C resolution (2026-06-25):**
- `pyproject.toml` now declares a `[project.dependencies]` array that mirrors
  `requirements.txt` exactly (incl. `cryptography>=42.0.0`), plus a
  `[project.optional-dependencies] dev` group and `[tool.setuptools.packages.find]`
  so the project is actually installable.
- **Proven on a fresh venv:** `pip install .` pulled `cryptography 49.0.0`
  (with cffi/pycparser) and the full GUI dep set; the fresh env imports
  `cryptography`, loads `cache_vault` 0.1.3, and evaluates a license to
  `MISSING_LICENSE` with the Ed25519 serialization path live (not failing
  closed). requirements.txt / pyproject / PyInstaller spec / `build_exe.ps1`
  are now consistent.
- The `pyproject.toml` package `description` was corrected from "local-only" to
  **"local-first"** (the Mobile Bridge is an opt-in LAN feature). The remaining
  "local-only" strings in `__init__.py`, docs, and landing pages are inventoried
  for the Phase G claim audit.
- One real gap the gate caught: the project `.venv` was missing `zeroconf`
  (tests passed anyway because its import is guarded). `scripts/ci_local_full.ps1`
  preflight **refused to claim PASS** until `requirements.txt` was installed.

---

## 2. What is implemented (in source, covered by tests)

| Area | Module(s) | Notes |
|---|---|---|
| Clipboard capture | `core/clipboard.py`, `core/capture_rules.py`, `core/vault.py` | Auto-capture on by default; pause/resume supported. |
| Classification | `core/classify.py`, `core/clip_metadata.py` | text / code / link / path / image / email / phone. |
| Sensitive auto-expiry | `core/sensitive.py` | **On by default** ("doctrine"); blocks sensitive auto-capture. |
| Quick Paste | `ui/` Quick Paste surface | **Free.** Not Founder-gated. |
| Safes / smart folders | `core/safes.py`, `core/smart_folders.py` | Local organization. Custom Safes are Founder-gated. |
| Receipts / stamped proof | `core/app_receipt.py`, `core/capture_receipts.py`, `core/macro_receipts.py` | Local proof receipts; see §6. |
| Exports | `core/export.py`, `core/exports.py`, `core/drag_export.py` | Advanced/zip/proof-pack/HTML-bundle exports are Founder-gated. |
| Editable copies / HTML bundles | `core/editable_copies.py` | Founder-gated (advanced). |
| Vault Macros | `core/vault_macros.py`, `core/macro_execute.py`, `core/macro_shortcut_listener.py` | Founder-gated (`macros_advanced`). |
| Command Center → Hotkey Actions | `core/command_center.py`, `ui/command_center.py` | **Phase 1 only.** **Free** (not gated). |
| Mobile Bridge | `core/mobile/*` | **Off by default**, LAN-only. See §5. |
| Settings | `core/settings.py` | Safe defaults + sanitizing load. See §7. |
| Licensing / Founder gate | `licensing.py`, `feature_gate.py` | Offline Ed25519, public-key-only in app. |
| Vault Lock | `core/vault_lock.py` | **UI privacy lock, not file encryption.** |

---

## 3. What is NOT implemented (reserved / future)

- **Command Center Phases 2-5:** Text Expansions, Quick Paste menu automation,
  full Vault Macro steps inside Command Center, and the Run Log UI screen. The
  local run log data exists; the dedicated UI does not.
- **Reserved Hotkey Action types** defined in `command_center.py` but
  intentionally **not** offered/executed: move-latest-to-safe, copy-selected,
  copy-selected-clean, paste-selected, toggle-mobile, export-selected,
  create-receipt. The editor only offers the 6 implemented actions.
- **App-only hotkey scope:** removed from the UI (Phase 1 hardening) because it
  would register globally and mislead the user. Only "Global" is offered.
- **No cloud sync, no accounts, no in-app payment** — and these are explicitly
  not claimed (`app_receipt.NOT_CLAIMED`).

---

## 4. Free vs Founder vs demo

### Free (no license required)
Core capture, classification, sensitive auto-expiry, Quick Paste, search, the
default Safe, Vault Lock, and **Command Center → Hotkey Actions**.

### Founder-gated (require a valid offline license)
`exports_advanced`, `zip_export`, `proof_pack_export`, `html_bundle_export`,
`editable_copies_advanced`, `smart_filters_advanced`, `macros_advanced`,
`safes_advanced`. Nav gates (`shell._FOUNDER_NAV_GATES`): Exports, Editable
Copies, HTML Bundles, Vault Macros.

Licensing is **offline**: an Ed25519-signed `license.json` under
`%LOCALAPPDATA%\CacheVault\`. The **private signing key never ships**; only the
public key is embedded. States: FREE, FOUNDER_VALID, INVALID_SIGNATURE,
WRONG_PRODUCT, CORRUPT_LICENSE, EXPIRED_LICENSE, MISSING_LICENSE.

### Demo-only
- `command_center.demo_actions()` / `seed_demo_actions()` — **action
  definitions only**, no clipboard content.
- `visual_smoke/*.png` screenshots are captured against an **isolated temp
  profile** with generic fixtures, never real clipboard history.

---

## 5. What Mobile Bridge actually does

- **Off by default:** `Settings.mobile_access_enabled = False`. It does **not**
  start silently.
- **LAN-only:** desktop-side HTTP API on port `8742` (configurable) for **paired
  Android devices on the same network**. No cloud, no internet relay.
- **Pairing is token-based** (`PairedDevice`, hashed tokens); pairing is a
  deliberate user action.
- **Direction:** primarily a **read/browse** API for the phone to view vault
  clips, plus a **mobile inbox** path for sends from the phone
  (`core/mobile/inbox.py`, capped at 20 MB bodies). The bridge class is
  described as "read-only" for clip data; the inbox is the send channel.
- **Marketing position:** the Founder MVP SKU **does not market mobile access**
  (`app_receipt.NOT_CLAIMED` lists "Mobile access (not marketed in Founder
  MVP)"). The capability exists in code but is not a claimed selling point.
- Threat model + contract: `docs/MOBILE_THREAT_MODEL.md`,
  `docs/MOBILE_API_CONTRACT.md`, `docs/MOBILE_ANDROID_DIRECTION.md`.

> **Claim tension to resolve (Phase G):** `__init__.py` and `pyproject.toml`
> describe Cache Vault as a "local-only clipboard vault". The Mobile Bridge is a
> **local-network** feature, not cloud — so "no cloud" holds, but **"local-only"
> is imprecise** given an opt-in LAN bridge. "Local-first" is the more accurate
> phrase. This is flagged, not yet changed.

---

## 6. What receipts actually prove (and do not)

`app_receipt.export_app_receipt()` writes a proof folder containing
`VERSION.txt`, `LICENSE_STATUS.txt`, `FEATURE_MATRIX.md`, `APP_RECEIPT.md`, and
`SHA256SUMS.txt`.

**They prove:** the app version, edition, enabled/disabled Founder features,
license state, build commit, Python/platform, and a SHA-256 checksum of each
receipt file — i.e. *what this install of Cache Vault recorded about itself*.

**They do NOT prove:** third-party notarization, a tamper-proof external chain,
or that historical clipboard data is cryptographically immutable. The
`SHA256SUMS.txt` lets a reader detect edits **to the receipt files**, not to the
vault database.

The app already ships an honest limitations list (`app_receipt.KNOWN_LIMITATIONS`):
Safes are organization **not encryption**; Vault Lock is a **UI privacy lock,
not file encryption**; Founder features need a valid offline license; no
payment/account system.

---

## 7. Settings & safety defaults (verified in `core/settings.py`)

- `auto_capture_enabled = True`, `capture_paused = False`
- `block_sensitive_auto_capture = True`, `sensitive_expiry_enabled = True`
- `mobile_access_enabled = False` (bridge off), port clamped to 1024-65535
- `vault_lock_enabled = False`
- Load path **sanitizes** values (clamps port, coerces bools, restores default
  safe/macro ids, bounds `max_auto_capture_bytes`) — corrupted/missing fields
  fall back to safe defaults rather than crashing.

---

## 8. Known limitations (consolidated)

1. Local-first desktop app; **no cloud sync, no accounts, no telemetry**.
2. The **only** network surface is the opt-in, LAN-only Mobile Bridge (off by
   default).
3. Safes are organization, **not encryption**.
4. Vault Lock is a **UI privacy lock**, not file encryption.
5. Founder features require a valid **offline** license.
6. Command Center is **Phase 1 only** (Hotkey Actions); Phases 2-5 are not built.
7. `cryptography` is a **required** dependency, bundled in the packaged `.exe`
   and now declared in `pyproject.toml` (Phase C). Dev/CI should install
   `requirements.txt` (or `pip install .`).
8. "local-only" wording is fixed in all product code and current public docs
   (Phase C.5 Chunk 1). Historical ``packaging/RELEASE_NOTES-v0.1.3-*.md`` and
   ``docs/releases/v0.1.3-*.md`` still contain "local-only" — these are
   version-pinned artifacts describing a past state and are intentionally not
   modified. The CI claim tripwire intentionally does not scan subdirectory
   docs; its scope is REPO-root ``*.md``/``*.html`` only. See
   ``scripts/scan_claims.py`` ``scan_docs()`` docstring for the full scope
   rationale.

---

## 9. Items to resolve in later hardening phases

- **Phase C (done 2026-06-25):** runtime deps declared in `pyproject.toml`,
  clean-env install proven, `scripts/ci_local_full.ps1` one-command gate added.
- **Phase C.5 Chunk 1 (done 2026-06-25):** atomic writes, `.bak`, corrupt-file
  quarantine, "local-only" → "local-first" wording, CI claim tripwire.
- **Phase C.5 Chunk 2 (next):** destructive-action confirmations, mobile
  bridge fail-closed, export/receipt fail-safes, with tests.
- **Phase G:** reconcile remaining "local-only" wording in historical docs;
  complete public claim audit.
- **Phase E:** capture per-subsystem runtime proof (this audit is code/test
  based, not yet a runtime walk-through of every subsystem).
