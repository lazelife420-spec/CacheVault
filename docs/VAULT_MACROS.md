# Vault Macros

Vault Macros is a saved macro/snippet vault inside Cache Vault. It is organized with **Macro Safes**, **smart filters**, and a **setup wizard** — not a flat snippet list.

**Macro Safes are logical folders only. They are not encrypted.**

## Setup wizard

First time you open **Vault Macros** (sidebar → Command → Vault Macros), the **Set up Vault Macros** wizard runs if setup is not complete.

Steps:

1. Choose default Macro Safe
2. Review starter Macro Safes (created once)
3. Choose macro menu hotkey (default `Ctrl+Shift+M`)
4. Choose default output mode (clipboard paste or keystroke)
5. Enable/disable text shortcuts and macro hotkeys
6. Clipboard restore after macro paste (off by default)
7. Sensitive macro confirmation (on by default)

Starter Macro Safes:

- Macro Safe
- Email Templates
- Saved Replies
- Code Snippets
- Commands
- Personal Templates

Existing user Macro Safes and settings are never overwritten.

## Smart filters

Core filters include All Macros, Favorites, Recently Used/Created/Edited, Disabled, Broken / Needs Attention, Hotkey Conflicts, No Trigger Assigned, trigger-type filters, and output-mode filters.

Content/type filters map to smart types: Email Templates, Saved Replies, Signatures, Addresses / Contact, Code Snippets, Commands, Forms / Fill-ins, Links, Personal Templates.

Safety/proof filters: Sensitive / Confirm Before Use, Has Receipts, Never Used, Failed Last Run, Imported, Exported, Missing Safe.

## Smart classification

When creating or editing a macro, **Suggest type from content** applies heuristics (email-like text, URLs, code patterns, commands, etc.). Classification is a **suggestion only** — you can override Safe and smart type. Existing macros are never silently moved.

## Templates

New from template:

- New blank macro
- Email signature
- Saved reply
- Address/contact block
- Code snippet
- Command snippet
- Date/time snippet
- Clipboard wrapper (`{clipboard}`)

## Inspector

The Vault Macros screen inspector shows name, Safe, smart type, trigger, output mode, enabled/favorite, usage, receipt count, and warnings (conflict, no trigger, sensitive confirmation, failed last run).

## Broken / Needs Attention

A macro appears in **Broken / Needs Attention** when it has hotkey conflicts, empty trigger/body, invalid output mode, missing Safe, last run failed, or unsafe sensitive settings.

## Live execution (Phase 6.1)

Vault Macros now run in daily use:

- **Macro menu hotkey** (default `Ctrl+Shift+M`) opens a picker at the cursor. `1`–`9`, Enter, or click runs a macro; Esc closes without changing the clipboard.
- **Per-macro hotkeys** run directly when unique; duplicate hotkeys open the picker filtered to those macros.
- **Text shortcuts** (e.g. `;sig`, `;email`) expand in the foreground app via backspace + clipboard paste by default.
- **Run** on the Vault Macros screen executes the selected macro into the last focused app (not Cache Vault itself).

### Output modes

| Mode | Behavior |
|------|----------|
| `clipboard_paste` (default) | Put expanded text on clipboard, restore focus, send Ctrl+V. Optional clipboard restore after paste. |
| `keystroke` | Type expanded text as simulated keystrokes (ASCII-focused, configurable delay). Large content is blocked; enable in Settings. |

### Variables (live)

`{date}`, `{time}`, `{datetime}`, `{clipboard}`, `{safe_name}`, `{item_id}`, `{newline}`, `{tab}`

Receipts and UI never store full expanded output or macro bodies.

### Settings toggles (live)

- Enable Vault Macros
- Enable text shortcuts
- Enable macro hotkeys
- Restore clipboard after macro paste
- Sensitive confirmation
- Keystroke mode + delay

### Execution receipts (metadata only)

- `macro_executed` / `macro_failed`
- `text_shortcut_expanded`
- `macro_hotkey_executed`
- `macro_picker_executed`
- `macro_blocked_sensitive`
- `macro_disabled_skipped`

Fields include macro id/name, Safe, trigger type/value, output mode, target window title (when detectable), content hash, clipboard restored flag — **not** full macro body or expanded secrets.

## Receipts (setup)

Event + file receipts (metadata only — no full macro body):

- `vault_macros_setup_completed`
- `macro_safe_created`
- `macro_template_created`
- `macro_smart_type_assigned`
- `macro_moved_by_user`
- `macro_conflict_detected`

## Search

Search matches macro name, description, Safe, trigger value, smart type, and tags. Content search is optional (`macro_search_content` in settings).

## Proof export

`export_macros_proof_pack()` writes a manifest JSON with macro metadata, Safe metadata, smart type, trigger metadata, output mode, enabled state, and receipt counts. **`includes_macro_body` is explicit** when body text is included in the export manifest.

## Known limitations

- **No macro recorder** — capture is manual (create/edit macros in the UI).
- **No mouse automation**, registry/admin commands, web automation, OCR, or Perfect Keyboard import.
- **Text shortcuts** use a best-effort keyboard hook; they may not fire inside Cache Vault fields or password controls (ES_PASSWORD style).
- **Keystroke mode** is ASCII-focused and slower; non-ASCII characters may fail.
- **`{selected_text}`** is not implemented yet.
- Macro Safes are not encrypted and must not be described as secure containers.
- Smart classification is heuristic, not ML — expect occasional mis-suggestions.

## Storage

- Settings: `%LOCALAPPDATA%\CacheVault\settings.json` (`vault_macros_*`, `user_macro_safes`)
- Macros: `%LOCALAPPDATA%\CacheVault\macros.json`
