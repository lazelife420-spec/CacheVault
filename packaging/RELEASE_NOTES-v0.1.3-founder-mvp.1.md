# Cache Vault Founder MVP v0.1.3-founder-mvp.1

This is a hotfix release for the Cache Vault Founder MVP.

## What changed

* Pinned **◆ Founder** above collapsible sidebar groups so the Founder screen remains visible even when sidebar sections are collapsed.
* Added **Settings → Import License…** so license import remains reachable even if sidebar groups are collapsed.
* Added an explicit packaging gate to fail release packaging if `cache_vault.ui.founder` is missing from the packaged executable.
* Added `cache_vault.ui.founder` to PyInstaller hidden imports.
* Preserved the existing Founder license flow, free tier, release receipt flow, and local-first product behavior.

## Why this release exists

The previous Founder MVP package included the Founder code, license system, and feature gates, but the Founder page could be hidden when the ACCESS sidebar section was collapsed in user settings.

That made the paid unlock flow hard to discover.

This hotfix makes the Founder screen immediately visible and keeps license import reachable from Settings.

## Verification

Automated packaged smoke passed:

* Free selftest
* Invalid license rejection
* Valid Founder license acceptance
* Proof receipt export with no clipboard data leak

Manual smoke required before public promotion:

* Open packaged ZIP build
* Confirm **◆ Founder** is visible immediately in the sidebar
* Confirm **Settings → Import License…** is visible
* Import a test Founder license through the UI
* Restart the app
* Confirm Founder remains active
* Export a release receipt
* Confirm the receipt does not include clipboard contents
* Leave app idle for 10 minutes
* Leave app running with Capture on for 10 minutes

## Known limitations

* No cloud sync.
* No mobile bridge claim.
* No account system.
* No automatic license server.
* Founder licenses are manually issued during the Founder MVP period.

## Product status

Cache Vault remains local-first.

The free version remains usable.

Founder Edition remains a one-time upgrade for advanced workflows.
