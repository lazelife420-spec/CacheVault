# Cache Vault — Release Closure Gate R2 Audit: Version Identity Reconciliation

**Date:** 2026-08-21
**Lane:** CLAUDE / CURRENT PROOF FOUNDRY
**Starting canonical:** `806d199a07e469ef294da1b7e9d0be0032fe0072` (branched fresh from `master`, not from the R1 evidence branch)
**Scope:** reconcile version identity and metadata/docs only. No build, no publish, no production-behavior change.

## Decision adopted (from the human, this gate reconciles it)

**Desktop release identity: `v0.2.1`.** Rationale (as directed): `v0.2.0` is already a historical published release; canonical `806d199...` contains substantial post-`v0.2.0` work plus a real correctness fix (Gate B); reissuing materially different content under the same `v0.2.0` version would destroy artifact identity.

## Old/unmerged Android `v0.2.1` artifact — declared non-authoritative

Evidence gathered this gate, beyond what R1 already found:
- The abandoned worktree's own git `HEAD` (`83019a652d3d6ba786f69a396aa1b80557224e9f`) is dated **2026-06-27** and is an **ancestor** of current canonical `master` — i.e. it is old, not diverged-new, work. `git merge-base --is-ancestor` confirms it.
- This means even the worktree's own checked-out source tree (if it were trusted) represents *older* content than canonical, not a legitimate `0.2.1`-worthy build.
- The `.apk` file's presence in that worktree's `dist/` output directory does not correspond to any coherent commit in its own git history — `dist/` is a build-output directory, and nothing ties that file's actual contents to a specific, auditable source state.

**Conclusion, recorded per instruction:** `CacheVault-Mobile-v0.2.1-android.apk` at `.claude/worktrees/great-swartz-cf2a02/dist/release/v0.2.1/` is **non-authoritative**. It must not be treated as proof that any `v0.2.1` Android build shipped, and it must not be reused as a release artifact.

## Android source `0.2.1` compatibility with current desktop protocol

Confirmed **compatible**, checked directly against the tracked (canonical) Android and desktop source — not the abandoned worktree:
- Desktop (`cache_vault/core/mobile/compatibility.py`): `MOBILE_PROTOCOL_MIN = MOBILE_PROTOCOL_MAX = 1`; `MINIMUM_MOBILE_VERSION = "0.1.0"` (a floor, not a target).
- Android (`android/app/src/main/java/.../data/AppIdentity.kt`): `PROTOCOL_VERSION = 1`.
- `1 == 1` → protocol-compatible. `"0.2.1" >= "0.1.0"` → clears the minimum-version floor.

**Note:** `compatibility.py` carries a comment ("...below the real shipped android/app/build.gradle.kts versionName (0.2.0 as of this writing)") that is now stale relative to the tracked `0.2.1` versionName. This is a **comment only — zero behavior impact** — and was deliberately **not touched** in this gate, since R2's authorized scope is README/CHANGELOG/RELEASE_NOTES/version metadata, not production source files (even comment-only edits). Flagged as a P2 for a future bounded pass.

## Must Android be rebuilt from canonical source?

**Yes.** The only artifact matching the `0.2.1` label is the non-authoritative worktree APK above. The tracked `android/app/build.gradle.kts` on canonical `master` already declares `versionName "0.2.1"` / `versionCode 8` — a genuine, current, canonical `0.2.1` Android artifact does not exist yet and must be produced by an actual build from canonical source. **Not performed in this gate** — R2's scope is identity/docs reconciliation only; the rebuild belongs to Release Closure's resumed Phase 2/5.

## Files changed and why

| File | Change | Why |
|---|---|---|
| `pyproject.toml` | `version = "0.2.0"` → `"0.2.1"` | Declares the desktop release identity |
| `cache_vault/__init__.py` | `__version__ = "0.2.0"` → `"0.2.1"` | Same — single source of truth, matches `pyproject.toml` |
| `README.md` | "Honest scope & limitations (current, v0.2.0)" → "(current, v0.2.1)" | Keep the honest-scope section's version label accurate |
| `CHANGELOG.md` | Renamed `## Unreleased` content to `## Cache Vault v0.2.1`, added a fresh empty `## Unreleased` above it, added the Gate B bridge-race fix to the Fixed list, updated commit count framing ("86+ commits... none tagged or released until now") | The content was already accurate and evidence-grounded (from Gate A); it just needed a real version header instead of sitting as `Unreleased` forever, and needed the Gate B fix folded in since that landed after Gate A wrote this section |
| `RELEASE_NOTES.md` | Added a new top section, explicitly headed "v0.2.1 (pending — not yet built, packaged, or published)" | Declares the identity **without** fabricating a shipped-release narrative — no device verification, no artifact claims, since none exist yet. Points to `CHANGELOG.md` for the itemized list |
| `docs/releases/v0.2.0.md` (new) | Added the missing historical receipt for the actual `v0.2.0` release | Closes the gap R1 found (every release `v0.1.6`–`v0.1.9` has one; `v0.2.0` didn't). Built entirely from evidence independently re-verifiable via `gh release view v0.2.0` / `gh api` (asset digests, release body) — no invented claims |

**Not touched:** `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` (its `0.2.1 external-test` framing is about the *Android/mobile-bridge Free-tier policy*, a separate, already-correct concern from the desktop version number — no change needed), `android/app/build.gradle.kts` (already correctly declares `0.2.1`, nothing to reconcile there), any production Python or Kotlin source beyond the two version-string files above, any test file.

## Website / download authoritative-source recommendation

**Not published or changed — recommendation only, per the "not build or publish yet" boundary.**

Of the three surfaces R1 found in conflict:
1. `docs/index.html`, served via GitHub Pages at the custom domain `theprooffoundry.com` — confirmed via `gh api repos/.../pages` to be live, built, and sourced from `master:/docs`.
2. The live Cloudflare Pages deployment at `cache-vault-landing.pages.dev`.
3. `downloads.theprooffoundry.com` — an undocumented third domain.

**Recommendation: `docs/index.html` (surface 1) should be the authoritative source.** It is the only one of the three whose content is actually tracked in this repository and therefore auditable through the same gated, evidence-based process as everything else in this project. The Cloudflare Pages deployment's source template was not found anywhere in this repo — meaning it is built/edited through some process outside this repository's version control, which makes it fundamentally un-auditable from here regardless of which one currently has fresher-looking content.

This is a recommendation for the project owner to accept or reject, not a decision this gate is authorized to execute. If accepted, the actual work (retiring or redirecting the Cloudflare Pages deployment, or bringing its source into this repo, and updating `docs/index.html`'s own stale `v0.1.9` pin) is Release Closure R1's resumed Phase 6, not R2.

## Validation

| Check | Result |
|---|---|
| `pyproject.toml` version | `0.2.1` (confirmed via `tomllib.load`) |
| `cache_vault.__version__` | `0.2.1` (confirmed via import) |
| Versions match each other | Yes |
| `git diff --check` | Clean |
| `app.py --selftest` | PASS — "core capture/classify/sensitive/image/mobile pipeline works" (no production behavior changed, sanity-checked anyway since a version-string import path was touched) |
| `python scripts/scan_claims.py` | Zero new findings in any file this gate touched — the only hit in `RELEASE_NOTES.md` is the pre-existing "No cloud" false-positive at its (now-shifted) original line, not new content |

## Not attempted (out of R2 scope, belongs to resumed R1)

Build, packaging, artifact verification, Android rebuild, checksum generation, website publication, stranger-install test.
