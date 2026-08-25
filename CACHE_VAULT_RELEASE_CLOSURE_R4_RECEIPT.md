# Cache Vault — Release Closure Gate R4 Receipt

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT PROOF FOUNDRY
**Disposition:** One bounded fix applied and proven (smoke test). Two items genuinely blocked on out-of-session facts (Android signing password, physical test device, GUI-automation limits). One item resolved definitively (public-surface authority). No rebuild performed — deferred to after canonicalization, per the stated chain.

## Starting canonical

`b92d960bd7acd282516adebb7338ecffa51b86ab`

## Branch / rollback tag

- Branch: `release/closure-r4`
- Rollback tag: `pre-release-closure-r4-2026-08-21`

## Item 1 — Android signing

Located **Backup 2** of the release keystore (`C:\Users\<account>\Documents\CacheVaultSigning-Backup\cachevault-mobile-release.jks.gpg`) — present, encrypted, recoverable. Password file absent; password never requested or entered, per the never-handle-credentials-in-chat rule. The documented decrypt/verify procedure is recorded verbatim in the audit doc for whenever the project owner supplies the password out-of-session. Not a lost key — a password-availability gap in this session only.

## Item 2 — Desktop↔Android interop

Not performed. Two independent blockers: no signed APK (Item 1), and `adb devices` shows no physical test device connected this session.

## Item 3 — Windows stranger walkthrough

Retried via File Explorer double-click (a different method than R3's `Start-Process`). **Confirmed the packaged exe launches and runs stably** (PID 21364, ~89MB, no crash, consistent with tray-based startup) — stronger evidence than R3. Interactive control remained impossible: this session's GUI-automation tooling could not resolve the running process as a controllable target, confirming the same limitation a second, independent way. Full interactive sequence remains `REQUIRED BEFORE PUBLICATION`.

## Item 4 — Smoke-test correction (fixed and proven)

`scripts/founder_package_smoke.ps1`'s two license-dependent steps were rewritten to call `cache_vault.licensing` directly (matching the script's own pre-existing pattern for its receipt-export check) instead of routing through `--selftest`'s intentional containment, which never saw the injected license file. **Proven correct, not just applied:** the fixed steps now genuinely discriminate — forged license → `INVALID_SIGNATURE`, real Founder license → `FOUNDER_VALID` + feature-enabled `True`. Full run: `4/4 PASS`. Zero product-code changes. `git diff --check` clean.

## Item 5 — Public-surface authority (resolved definitively)

`landing.html` (the actual Cloudflare Pages deploy source, per R3) contains its own `<link rel="canonical">` and `og:url` both pointing at `https://cache-vault-landing.pages.dev/` — the page names itself. Combined with R3's DNS evidence (`theprooffoundry.com` → Cloudflare IPs, not GitHub Pages IPs), this is now a definitive, not merely high-confidence, finding. `docs/index.html` is classified **LEGACY/ORPHANED**. `downloads.theprooffoundry.com` is explained in `landing.html`'s own copy as a deliberate GitHub-Releases mirror, resolving R1's original "UNKNOWN" classification. **Recommendation (not executed): `landing.html`/Cloudflare Pages should be the authoritative surface going forward** — reverses R2's original `docs/index.html` recommendation. No website file edited or published.

## Item 6 — Final candidate

Only the bounded, justified change (the smoke-test fix) plus this gate's three deliverable documents were committed. No rebuild performed in this gate — per the stated release chain, the one final deterministic rebuild happens once, after these tracked changes are canonicalized.

## Files changed

`scripts/founder_package_smoke.ps1` (test script only, zero product code), plus `CACHE_VAULT_RELEASE_CLOSURE_R4_AUDIT.md`, `_SUMMARY.json`, this receipt.

## Validation

| Check | Result |
|---|---|
| `git diff --check` | Clean |
| `founder_package_smoke.ps1` full run | 4/4 PASS, genuinely discriminating (see Item 4) |
| Working tree scope | Exactly the 4 files above |

## Custody confirmation

All 9 prior rollback tags intact. Preservation branch unchanged. R1/R2/R3 branches untouched. `master` remains exactly `b92d960...`. No `v0.2.1` tag or GitHub Release created. Nothing pushed. No website published.

## Still outstanding (not fabricated as complete)

Android signing-key decryption (needs the project owner + password, out of this session), the resulting signed APK build, physical-device interop test, the full interactive Windows stranger walkthrough, and the project owner's sign-off on the public-surface recommendation. One final deterministic Windows+Android rebuild is still owed once all tracked changes (R3's Windows evidence + R4's test fix) are canonicalized together.
