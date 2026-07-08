# Cache Vault v0.1.7

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.7

### Paste Macro One-Shot UX
- **Create Paste Macro from selected clip** — right-click a clip or use the preview panel to open the macro editor prefilled with the clip's title and body. Set a hotkey, save — the macro is immediately active and pastes anywhere in the system (PR #39).
- **Save to Snippet Macros** remains available as the silent/secondary path with no dialog.

### Bug Fix — Keyboard Focus Crash
- **`_keyboard_focus_is_text_input` string path resolution** — when focus was inside a `CTkToplevel` dialog (such as the macro editor), Tkinter passed the focused widget as a hierarchical string path rather than a widget object. This caused an `AttributeError` followed by a `TclError: bad window path name` crash visible to users as an Application Error dialog. Fixed by resolving string paths via `nametowidget` with exception safety (commit `30d942e`).

### QA Basis
- Automated packaged Paste Macro QA: selected clip → MacroEditDialog prefilled → Ctrl+8 hotkey recorded → saved → pasted cleanly in Notepad (compiled EXE).
- 838-test suite: PASS.
- `compileall`: PASS. `--selftest`: PASS.
- `v0.1.6` tag: unchanged at `6f316a9`.

See `CHANGELOG.md` "Cache Vault v0.1.7" for the full itemized list.

---

# Cache Vault v0.1.6

**Cache Vault by The Proof Foundry™** — local-first Windows clipboard vault.
No cloud account. No subscription.

> `/proof` is unchanged unless separately approved. Nothing in this document
> is a "stable" claim beyond what is explicitly stated below.

## What is new in v0.1.6

### Home Redesign
- **Redesigned Hero stats tiles and status pills** — redesigned home dashboard hero showing status pills and custody stats tiles, and a cleaner window toolbar header with a 2px teal accent line (PR #34).

### Sidebar & Context Menus
- **Sidebar right-click context menus** — added right-click context menus for headings (expand/collapse options), individual safes (full management options like delete, rename, etc.), the Founder badge, and macro/paste rows (PR #33).
- **Default-collapsed groups & order stability** — default-collapsed categories for new profiles, and stabilized heading ordering (PR #31).
- **Parity select** — toolbar actions match right-click context menu options for single/multi clip selection (PR #26).

### Keyboard & Hotkeys
- **Numpad hotkey correctness** — preserved numpad identity in hotkeys (e.g. distinguishing Ctrl+Numpad2 from Ctrl+2) (PR #32).
- **Hotkey recorder fixes** — focus and window-ownership stability fixes for the hotkey recorder.

### Internal QA
A full packaged-EXE QA pass is recorded in
`docs/CACHE_VAULT_PACKAGED_DESKTOP_QA_RECEIPT_2026-07-07.md`: selftest,
founder license smoke, packaged GUI checks, Settings Hub hotkey recording, selection parity, and visual layout polish all passed. Final public checksums are
provided in `SHA256SUMS.txt` attached to the release.

See `CHANGELOG.md` "Cache Vault v0.1.6" for the full itemized list.

## Previous release: v0.1.5

v0.1.5 (`cache-vault-v0.1.5-release.1`) was the previous public release.
See `packaging/RELEASE_NOTES-v0.1.5.md` for its notes, or `CHANGELOG.md` for
the full historical entry.

## Trust

- **Local-first** — no cloud sync, no accounts, no telemetry.
- **No internet connections.** Optional LAN bridge is off by default and never
  calls home.
- **Offline license verification** — Ed25519 public-key check only; no license
  server.
- **Manual Founder license delivery** — no in-app payment in this build.
- Windows executable is **unsigned**. Verify against `SHA256SUMS.txt` from the
  public `lazelife420-spec/CacheVault` release before running.

## Verification

| Check | Result |
|---|---|
| `pytest` | 803 passed |
| `compileall cache_vault` | PASS |
| `app.py --selftest` | PASS |
| GitHub Actions matrix | 3.12 ✓ · 3.13 ✓ |
| Founder package smoke | PASS |
| Published checksums | See `SHA256SUMS.txt` attached to this release. |

## Artifacts

- `CacheVault-v0.1.6-windows.zip`
- `SHA256SUMS.txt`
