# Cache Vault v0.1.5-rc1 — Release Notes

**Status:** Release Candidate (not final public release)
**Base:** v0.1.4 release.1 (public proof release)
**Branch:** `ux/mobile-image-polish-local`
**Date:** 2026-06-30

---

## What's New

### Workflow Features

- **Selected Item Paste Workflow** — Right-click any clip → Paste Selected Item delivers it to the foreground app via Ctrl+V. Focus safety guards prevent accidental self-paste into Cache Vault.

- **Copy Selected Item to Safe** — Non-destructive duplication: right-click → Copy to Safe creates a new copy in the target Safe while preserving the original clip, including any image assets.

- **Copy to Last Safe** — Quick shortcut to copy a clip to the most recently used Safe without opening the picker.

- **Do Not Save Next Copy** — One-shot privacy bypass: arm the toggle, and the next clipboard copy is silently skipped. The bypass resets after one use or after 60 seconds. Does not interfere with paste or copy-to-safe workflows.

### UI Polish

- **Date Stamp Readability** — Clip timestamps now display as `Jun 30, 6:24 PM` with full ISO tooltips on hover.

- **Image/Screenshot Preview Polish** — Image previews render inside a `vault_card` styled frame at 340×250 with original filename, dimensions, and file size metadata.

- **Context Menu Organization** — Clip right-click menus now use cascaded submenus for Copy Clean, Organize, Proof, Advanced, and Danger groups. Primary actions (Copy, Paste, Open Link) remain flat at the top for quick access.

- **Settings Panel Cleanup** — Advanced settings sections (Vault Lock, History & Pruning, Sensitive Clips, Snippet Macros) are now clearly labeled with "Advanced:" prefix for visual separation.

---

## Test Proof

| Gate | Result |
|---|---|
| `pytest -p no:xonsh` | **785 passed** |
| `python -m compileall cache_vault` | **PASS** |
| `python app.py --selftest` | **PASS** |

## Integration Audit

| Flow | Verdict |
|---|---|
| Selected paste + focus safety | **PASS** |
| Copy-to-Safe interaction | **PASS** |
| Do Not Save Next Copy interaction | **PASS** |
| Date/image preview regression | **PASS** |
| Menu honesty | **PASS** |
| Release proof regression | **PASS** |

Integration audit: 25/25 tests passed (`tests/test_workflow_integration.py`)

## Manual/Visual QA Receipts

- `docs/SELECTED_ITEM_PASTE_QA_2026-06-30.md`
- `docs/COPY_TO_SAFE_WORKFLOW_QA_2026-06-30.md`
- `docs/DO_NOT_SAVE_NEXT_COPY_QA_2026-06-30.md`
- `docs/DATESTAMP_IMAGE_VIEWER_POLISH_QA_2026-06-30.md`
- `docs/MENU_SETTINGS_CLEANUP_QA_2026-06-30.md`
- `docs/CACHE_VAULT_WORKFLOW_INTEGRATION_RC_AUDIT_2026-06-30.md`

---

## Holds

- Not yet published to Proof Foundry `/proof`
- No public hash until package artifact is built and verified
- No git tag until final RC gate passes and user approves
- Branch name (`ux/mobile-image-polish-local`) does not reflect full scope — acceptable for RC

---

## Commit Range

```
e6fe972 chore: reconcile Cache Vault public release proof surface
caa8604 feat: add selected item paste workflow
c893ade chore: add selected item paste workflow QA receipt
6b58dc8 feat: add selected item copy-to-safe workflow
f4a8f5e feat: add do-not-save next copy workflow
4bc32de feat: polish date stamps and image preview viewer
1a8dcdd feat: clean up menus and settings organization
d4f5d26 chore: add Cache Vault workflow integration RC audit
```
