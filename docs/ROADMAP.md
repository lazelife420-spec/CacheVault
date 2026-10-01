# Cache Vault — Roadmap

Living document, started 2026-10-01 after the v0.3.1 release. Every line below
is a verified fact or a verified open item with its evidence. Historical phase
plans live in `docs/FOUNDER_MVP_BASELINE_AUDIT.md` (all five MVP phases shipped,
2026-06-19) and `docs/RELEASE_READINESS_RC_NEXT.md` (the v0.1.3-rc6 readiness
audit) — treat those as records, not plans.

## Current state (verified 2026-10-01, v0.3.1)

- **Windows**: v0.3.1 is the public release (commit `eddbae7`, tag `v0.3.1`,
  published 2026-10-01). Release gate: local CI suite 2120 passed / 1 skipped /
  0 failed, plus the CI-gate grace fix (`review/CV-CI-SANDBOX-GRACE-20260930/`).
  The exe is unsigned; the published ZIP SHA-256 is the verification anchor
  (GitHub Releases and `downloads.theprooffoundry.com`).
- **Android companion**: v0.3.1 (versionCode 10) is public on GitHub Releases
  and the Proof Foundry mirror. Release-signed, certificate SHA-256
  `c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c`
  (apksigner-verified). Ships the standalone phone-local vault and on-device
  capture: "Save last copy" notification, on-open drain, screenshot
  auto-import, sensitive auto-block on by default.
- **Device proof**: phone-local vault and capture lanes PASS 9/9 on SM-S911W
  (Android 16 / SDK 36, 2026-09-30;
  `review/CV-MOBILE-CAPTURE-TM-20260930/results_phone_smoke_s23.json`).
  The paired-companion lane is **not** device-proven.
- **Public site**: `theprooffoundry.com` carries v0.3.1 truth (deployed
  2026-10-01 from the `pf-cv031-truth` landing).

## Open items (verified, not yet done)

1. **Paired-companion hardware smoke.** Pair a physical phone with the v0.3.1
   desktop build and run the pass/fail checklist in `android/README.md` for the
   PC companion browsing lane. `android/README.md` forbids calling the paired
   lane device-proven until this runs; the 2026-09-30 device pass covered the
   phone-local vault and capture lanes only.
2. **Retire the stale S3 upload script.** `scripts/s3_upload_release.ps1`
   targets AWS S3, but the live mirror is Cloudflare R2 (bucket
   `proof-foundry-downloads`; the AWS CLI is absent and release objects were
   uploaded with `wrangler r2 object put`). Rewrite it for R2 or delete it so
   the next release does not follow a dead path.
3. **Site-repo reconciliation debt (cross-repo).** The `proof-foundry-site`
   guards carry pre-existing reds that predate the v0.3.1 site landing: the
   lights-out landing left its custody migrations and source pins un-updated
   (`products/lights-out/content.html`, `support.html`,
   `products/lights-out/module.json`, `h9-homepage.js`) and the live verifier's
   lights-out "candidate companion" expectation fails; the in-flight editorial
   asserts (`h2`/`h3`/`h7a`/`h9-homepage`/`signature-home`/footer link) are red
   at the site repo's committed HEAD `532cae1` too. Baseline evidence: a
   pristine worktree at `532cae1` fails the identical set. Schedule this with
   the site repo's product-capsule migration before the next site landing.

## Explicitly not claimed (until shipped or proven)

- Command Center beyond Phase 1 (Hotkey Actions).
- Paired-companion lane device-proven status (see open item 1).
- Silent background clipboard capture on Android: the platform denies
  clipboard reads to any app without window focus, so capture is
  notification-mediated or focus-gated by design
  (`docs/MOBILE_THREAT_MODEL.md`).
