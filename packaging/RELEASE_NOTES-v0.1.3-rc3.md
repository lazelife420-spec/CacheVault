# Cache Vault v0.1.3-rc3 (release candidate)

**Status:** Release candidate — not a final release. **No git tag.** Do not replace the shipped **v0.1.2** desktop release.

## Scope

### Desktop (Windows exe in this zip)

Everything in **v0.1.3-rc2**, plus Vault Macros live execution:

- **Vault Macros** — create/edit macros, triggers, output modes, run counts, smart filters
- **Text shortcuts** — type a shortcut (e.g. `;sig`) in any app to expand macro body
- **Global macro hotkeys** — per-macro hotkey bindings
- **Macro picker** — `Ctrl+Shift+M` opens picker at cursor; number/Enter executes; Esc closes safely
- **Paste/type delivery** — macro body lands in foreground app, not Cache Vault window
- **Execution receipts** — audit trail without storing full sensitive macro body
- **Optional clipboard restore** after macro paste
- **Run button stability** — no CTk error dialog after macro run refresh

Also includes everything from rc2: Command Center, Capture Rules, Safes, proof export zip, editable copies, HTML bundles, Mobile Access screen.

**Safes are not encrypted.** Whole-Safe export UI is deferred; manifest schema is ready.

### Mobile companion (Android app — separate artifact)

Requires **Mobile Access ON** on the PC running this build:

- Read-only LAN bridge on port **8742**
- Pairing, vault browse, image thumbnails, proof/settings screens
- Clip payloads include Safe metadata when present

Install the matching Android APK from the same branch build; it is **not** inside this Windows zip.

## What changed since v0.1.3-rc2

| Area | Change |
|------|--------|
| Vault Macros | Setup UI + smart filters (Phase 6) |
| Live execution | Hotkeys, text shortcuts, picker, paste/type (Phase 6.1) |
| Receipts | Macro execution events; no sensitive body leak |
| Stability | CTk crash-dialog fix after Run button refresh |
| Version | `0.1.3-rc3` (RC only — not final) |

## Artifacts (this RC)

- `CacheVault-v0.1.3-rc3-windows.zip`
- `SHA256SUMS.txt`
- `docs/releases/v0.1.3-rc3.md`

## Explicit non-actions

- **No** git tag unless explicitly approved after proof
- **No** GitHub release publish
- **No** modification of shipped v0.1.2 artifacts
- Root `README.md` and `RELEASE_NOTES.md` remain **v0.1.2** (shipped desktop truth)
