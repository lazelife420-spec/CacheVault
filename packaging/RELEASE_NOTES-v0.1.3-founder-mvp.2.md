# Cache Vault Founder MVP v0.1.3-founder-mvp.2

Hotfix release for Vault Macros, Quick Paste screenshots, and clipboard reliability.

## What changed

* **Vault Macros setup** — fixed Macro Template Picker crash (`TclError` on focus) during setup.
* **Vault Macros Run** — withdraws Cache Vault briefly so keystrokes reach the target window; clipboard-only success when no target is focused.
* **Save to Vault Macros** — preview panel and toolbar path to save clips as macros; auto minimal setup when wizard is incomplete.
* **Quick Paste screenshots** — image copy sets **CF_DIB + PNG** for broad app compatibility; copy deferred after Quick Paste closes (no grab conflict).
* **Quick Paste UX** — branded **Copy Image to Clipboard** action; screenshots copy to clipboard only (no auto-paste).
* Includes all **v0.1.3-founder-mvp.1** Founder discoverability fixes (pinned ◆ Founder nav, Settings → Import License…).

## Verification

Automated packaged smoke (run before manual gate):

* Free selftest
* Invalid license rejection
* Valid Founder license acceptance
* Proof receipt export with no clipboard data leak

Manual gate required before public promotion — see `docs/FOUNDER_FIRST_SALE.md`.

## Known limitations

* No cloud sync, mobile bridge claim, account system, or automatic license server.
* Founder licenses are manually issued during the Founder MVP period.
