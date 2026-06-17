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

## Receipts

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

- Macro hotkey execution and text-shortcut expansion are **settings + data model only** in this phase; live global trigger dispatch is not fully wired.
- Keystroke output mode is declared but not executed against foreground apps yet.
- Macro Safes are not encrypted and must not be described as secure containers.
- Smart classification is heuristic, not ML — expect occasional mis-suggestions.

## Storage

- Settings: `%LOCALAPPDATA%\CacheVault\settings.json` (`vault_macros_*`, `user_macro_safes`)
- Macros: `%LOCALAPPDATA%\CacheVault\macros.json`
