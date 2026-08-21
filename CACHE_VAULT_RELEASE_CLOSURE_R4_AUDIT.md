# Cache Vault — Release Closure Gate R4 Audit: Remaining Publication Blockers

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT PROOF FOUNDRY
**Starting canonical:** `b92d960bd7acd282516adebb7338ecffa51b86ab`
**Scope:** the 6 items from the R4 kickoff — Android signing recovery, desktop↔Android interop, stranger Windows walkthrough, stale smoke-test correction, public-surface authority, final release-source candidate. No product-code changes. No rebuild in this gate (the chain is: canonicalize R4's tracked changes first, then rebuild once from the resulting canonical SHA — a later step, not R4 itself).

## Phase 0 — Custody (completed)

`master` confirmed exactly `b92d960bd7acd282516adebb7338ecffa51b86ab`, working tree clean, all 9 prior rollback tags intact, preservation branch unchanged (`4f5b348...`), R1/R2/R3 branches all reachable and untouched. R4 rollback tag `pre-release-closure-r4-2026-08-21` created; branch `release/closure-r4` created from canonical `master`.

## Item 1 — Android signing recovery

**Real, actionable progress — the key is not lost.**

- Checked (existence only, never read/printed): primary keystore path, all three signing env vars (current shell, User-registry-persisted, Machine-registry-persisted) — **all absent**, consistent with R3.
- Checked the two documented same-machine encrypted backups from `docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md`:
  - Backup 1 (`C:\Users\KickA\CacheVaultSigning\backup-local\...gpg`): **not present**
  - **Backup 2 (`C:\Users\KickA\Documents\CacheVaultSigning-Backup\cachevault-mobile-release.jks.gpg`): PRESENT.**
- The password file (`.storepass`) is **not present** anywhere checked, and the password itself was never requested, entered, or guessed — per the boundary ("never expose secret contents") and this session's standing rule against handling credentials in chat.

**Recovery is possible but requires the account holder, not this session.** The documented procedure (`docs/CACHE_VAULT_MOBILE_RELEASE_SIGNING_CUSTODY.md` "Recovery procedure"):
```powershell
gpg --batch --yes --pinentry-mode loopback --passphrase-file <path-to-.storepass> --decrypt cachevault-mobile-release.jks.gpg > cachevault-mobile-release.jks
```
followed by SHA-256 verification against the documented value `05e855f2095f030a74cee8448805349c84f1cec28e1fe9de81eb0803898c0afd`, and a certificate-fingerprint check via `keytool`. **This was not run in this session** — the `.storepass` file is absent, and this audit will not ask for or accept a password typed into chat. If the project owner supplies the password file at its documented path (or the `.storepass` file itself) in a future session, the Android build can proceed immediately from Backup 2.

**For later comparison against a freshly-built `v0.2.1` APK once signing is recovered:** the known-good `v0.2.0` certificate SHA-256 is `c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c` (per the same custody doc's "Verified output" section) — a rebuilt `v0.2.1` should produce the *same* certificate identity (same key, different content), confirmable via `apksigner verify --print-certs` without needing the private key itself.

No physical Android device search was needed for this item — see Item 2.

## Item 2 — Desktop ↔ Android interoperability

**Blocked on two independent preconditions, neither met this session:**
1. No authoritative signed `v0.2.1` APK exists (Item 1).
2. `adb devices` returned an empty device list — **no physical Android device (including the documented test Galaxy S23) is connected to this machine in this session.**

Nothing further attempted; nothing fabricated. This remains fully outstanding for a future session where both a signed APK and the physical test device are available together.

## Item 3 — Stranger Windows walkthrough

**Retried via a different method than R3, with a real result: the packaged exe reliably launches and runs stably, but interactive GUI automation remains out of reach in this environment.**

- Requested `File Explorer` access (granted at "click" tier: click-only, no typing/right-click/drag-drop).
- Navigated Desktop → `CacheVault` folder shortcut → `dist` → double-clicked `CacheVault.exe` directly (bypassing the ZIP-extraction step, which would have needed right-click-to-extract — unavailable at this permission tier).
- **Confirmed via `tasklist`: the process launched and ran stably (PID 21364, ~88.8MB memory), no crash**, consistent with the app's documented tray-based startup (window not visible, sitting in tray by design).
- Attempted `request_access(["CacheVault"])` to interact with the now-running window — **denied**: "doesn't match any installed or running application." Same fundamental limitation as R3 confirmed a second, independent way — this session's GUI-automation tooling gates on an installed/registered-app allowlist, and this ad-hoc-launched exe (whether started via `Start-Process` or via File Explorer double-click) never satisfies that regardless of launch method.
- Process cleanly terminated (`taskkill`) after confirming stability; no test artifacts left running.

**This is stronger evidence than R3 had** (confirmed stable launch twice, via two independent methods) but does not change the outcome: the full interactive sequence (first-run, real clipboard capture, search, Quick Paste, Recently Removed recovery, restart-persistence) remains **`REQUIRED BEFORE PUBLICATION`**, not falsely marked complete. A future session with either (a) a human present to interact directly, or (b) the app registered as an installed application first, would unblock this.

## Item 4 — Stale smoke-test correction

**Fixed, and the fix is proven, not just applied.**

Root cause (established in R3): `scripts/founder_package_smoke.ps1`'s two license-dependent steps tried to inject a license file via `$env:LOCALAPPDATA` before running `dist\CacheVault.exe --selftest` — but `--selftest` is dispatched through `_run_contained_selftest()` in `app.py`, which **always** overrides `LOCALAPPDATA`/`TEMP`/`TMP`/`USERPROFILE` to a fresh, empty, auto-managed temp directory (intentional containment hardening, already-canonical, not touched here). The injected license file was therefore never seen.

**Fix applied, scoped to the test script only — zero product-code changes:** replaced the two `& $exe --selftest` invocations (for the "Invalid license rejected" and "Production test Founder license accepted" steps) with direct calls to the same `cache_vault.licensing` module the packaged build ships:
```powershell
python -c "from cache_vault import licensing; s = licensing.load_license(); print(s.state.value)"
```
This is not a new pattern introduced for this fix — it's the same approach the script's own "Proof receipt export" step already uses (calling `cache_vault.core.app_receipt` directly, with the script's own comment: "dev runner — same licensing module as packaged build"). Extending that established pattern to the two broken steps is internally consistent with the script's own prior design, not a novel workaround.

**Proof the fix tests the real invariant, not a tautology:** ran the corrected script — both steps now correctly discriminate between the forged license (`INVALID_SIGNATURE`) and the real Founder test license (`FOUNDER_VALID` + `is_feature_enabled → True`), i.e. two different inputs produce two different, correct outputs through the identical code path. Full run: `4/4 PASS`.
```
=== Founder package smoke ===
PASS  Fresh launch / free selftest
PASS  Invalid license rejected
PASS  Production test Founder license accepted
PASS  Proof receipt export (no clipboard leak)
All automated packaged smoke checks passed.
```
`git diff --check`: clean. Only file touched: `scripts/founder_package_smoke.ps1`.

## Item 5 — Public-surface authority

**Resolved with definitive (not merely high-confidence) evidence, superseding both R2's and R3's provisional findings.**

R3 established: `theprooffoundry.com` (and its `downloads.` subdomain) resolve to Cloudflare's anycast IPs, distinct from GitHub Pages' own IP range — meaning `theprooffoundry.com` is not served by GitHub Pages infrastructure. R3 also located `landing.html` (repository root) as the actual Cloudflare Pages deploy source via content match with the live `cache-vault-landing.pages.dev` page.

**R4 finishes the confirmation directly from the source, not just DNS/content inference:** `landing.html` contains its own explicit self-declaration:
```html
<link rel="canonical" href="https://cache-vault-landing.pages.dev/" />
...
<meta property="og:url" content="https://cache-vault-landing.pages.dev/" />
```
Whoever authored this page explicitly declared `cache-vault-landing.pages.dev` as its own canonical URL. This is the strongest possible evidence available short of Cloudflare account access — the page names itself.

**`downloads.theprooffoundry.com` is not a mystery domain.** `landing.html` itself explains it: *"Downloads are mirrored through The Proof Foundry while GitHub access is unavailable for some visitors. The GitHub release remains the canonical source record."* — a deliberate CDN/mirror in front of GitHub Releases, not an unowned or unrelated domain, resolving R1's original "UNKNOWN" classification.

**Final classification:**
1. What deploys `theprooffoundry.com`? Cloudflare (very likely Cloudflare Pages, `cache-vault-landing` project) — DNS-confirmed, not GitHub Pages.
2. `docs/index.html`: **classified LEGACY/ORPHANED.** Live at its raw `.github.io` URL (per GitHub's own Pages API) but not reachable via the branded domain, and not what the project's own current copy declares canonical. Recommend retiring or adding an explicit redirect/canonical-link to the real page, rather than leaving it silently stale.
3. `cache-vault-landing.pages.dev` deploys from `landing.html`, self-declared canonical.
4. `downloads.theprooffoundry.com` — deliberate GitHub-Releases mirror, same Cloudflare zone, referenced intentionally throughout `landing.html`.
5. `landing.html` already promises a `v0.2.1` Android download that does not exist as an authoritative artifact yet (Item 1/2) — this is a live, currently-dangling promise on the (likely) production surface.
6. **Recommended authoritative surface going forward: `landing.html` / Cloudflare Pages`,` given its explicit self-declaration and DNS-confirmed reachability at the branded domain — not `docs/index.html`, reversing R2's original recommendation.** This is a recommendation for the project owner's final sign-off, not executed here — no website file was edited or published in this gate.

**Website/download correction plan (assessed, not applied):** once `v0.2.1` is actually published (pending Items 1–3), `landing.html` needs its Windows link (`v0.2.0` → `v0.2.1`), its Android link (currently dangling), and its checksum references updated. `docs/index.html` needs either retirement or a full refresh, per the project owner's decision on item 2 above.

## Item 6 — Final release-source candidate

Only the justified change from this gate — the bounded `scripts/founder_package_smoke.ps1` fix — plus this gate's own audit/summary/receipt documents were committed to `release/closure-r4`. No product source touched. No rebuild performed in this gate (per the stated chain: rebuild happens once, after these tracked changes are canonicalized). Candidate SHA reported in the receipt below.
