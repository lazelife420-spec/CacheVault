# Cache Vault v0.2.1 — Final Release Proof Receipt

```
Canonical source SHA:      78f828281de20ed5787f953fee9f5093865abffc
Canonical tree:             5b38257505f3276750f2b036ede98394662ccfc8
Release version:            0.2.1

Build environment:          Windows 10.0.19045.6466, Python 3.13.2,
                             PyInstaller 6.16.0, Java 17.0.19, Gradle 8.7,
                             Android SDK build-tools 35.0.0, adb 1.0.41

Windows artifact:            CacheVault-v0.2.1-windows.zip
Windows SHA-256:             fdfbe69d421fa4c2a39f0cf2aa8ed914113430794b640c299fd3acddec717d37
Windows signing state:       Unsigned (disclosed policy)

Android artifact:            CacheVault-Mobile-v0.2.1-android.apk
Android SHA-256:              c085758f6ec6fe5801704c7d595f8926ed85e23ec8c6d10109ac36002f35e32b
Android certificate SHA-256:  c2eb5c42a684326ceba1289e65e9690ed71daf770de64e2b83a42bce04026a2c
                               (exact match, production key, same as published v0.2.0)
Android versionName/versionCode: 0.2.1 / 8

S23 device:                  Samsung Galaxy S23, serial R3CW40FY82W
Interop result:               PASS - mDNS discovery, pairing, authenticated
                               read operations, disable (0.616s, bounded),
                               re-enable all verified on live hardware

Stranger walkthrough result:  PARTIAL - SHA-256 verify, launch/no-crash,
                               packaged smoke all PASS; interactive GUI
                               steps NOT TESTED (tooling limitation)

Website source:                landing.html / Cloudflare Pages (recommended
                                authoritative, not yet formally adopted)
Download-source policy:        GitHub Release = canonical source record;
                                downloads.theprooffoundry.com = disclosed
                                mirror

Checksum file:                dist/release/v0.2.1/SHA256SUMS.txt

Known limitations:
  - Interactive Windows GUI walkthrough not completed this session
  - Website/download patchset prepared, not published
  - docs/index.html retire-or-reconcile decision deferred to project owner
  - E4b deferred, no evidence requiring it

P0:  0 (product), 0 (release) - the unsigned first Android build attempt
     was diagnosed, corrected, and re-verified signed within this same
     gate; nothing remains open
P1:  3 - see audit for detail (interactive walkthrough, website patchset,
     docs/index.html decision)
P2:  2 - E4b, one stale comment (zero behavior impact)

Publication status: READY FOR PUBLICATION AUTHORIZATION, WITH ONE BOUNDED
                     P1 (interactive Windows walkthrough) RECOMMENDED
                     BEFORE ACTUAL PUBLICATION
```

## Narrative summary

Both `v0.2.1` release artifacts now exist, are hashed, and are independently verified from canonical source `78f8282...`. Windows was built fresh (not reused from R3) and passed every automated/packaged check, including the now-corrected, genuinely-discriminating licensing smoke test. Android went through a real operator-assisted secret boundary: the human ran the signing-invocation build in their own process-scoped session, and this audit independently verified the *result* — certificate, hashes, signing scheme, package identity, and content provenance — without ever seeing the password.

The Android build's first attempt silently produced an unsigned artifact. This was consistent with Gradle daemon environment reuse (an idle daemon predated the build) — an evidence-supported diagnosis, not a directly proven cause, since the daemon's actual captured environment was never inspected. Reported precisely as the leading hypothesis; stopping the daemon and rebuilding with `--no-daemon` in the operator's signing environment produced the correctly signed release artifact.

Real interoperability was proven against the actual physical test device — not simulated, not against the historical stale APK — including a live exercise of the exact Gate B disable/force-stop invariant (bounded at 0.616s) under real network conditions.

One integrity correction was made during this gate: a prior evidence receipt's claim that the historical S23 APK was missing a current feature was discovered to be a tooling artifact (unreliable `strings`-based dex parsing) and was corrected in place, with the original wrong claim preserved and retracted rather than silently deleted.

The only genuine gap is the interactive Windows GUI walkthrough (first-run, capture, search, Quick Paste, Recently Removed, restart-persistence), which this environment's tooling still cannot drive against an unregistered packaged executable. Everything else required for a truthful `v0.2.1` publication is proven.

## Deliverable hashes

Computed via `certutil -hashfile ... SHA256`, after the daemon-wording correction below was applied (so these hashes reflect the final committed content):

```
cd87da3138343251f22ee66c100fd2726125af002580f4f43ca1fef3a2d96615  CACHE_VAULT_FINAL_RELEASE_PROOF_AUDIT.md
811560f31cd94f5e6ad4a0f152f1531418ba5a15da90af8a9851f81dad45d919  CACHE_VAULT_FINAL_RELEASE_PROOF_SUMMARY.json
7caa3abfab0dd0e7888d698092e64d09d52e46a1df4fdeb7bf9e1b2b62191ba6  dist/release/v0.2.1/SHA256SUMS.txt
```

This receipt's own SHA-256 cannot be embedded in itself (self-referential); it is computed and reported in the chat response accompanying the commit that includes this file, immediately after that commit lands.

## Not performed

Tagging, GitHub Release creation, asset upload, website publication, `git push`. All await separate authorization.
