# CV-MOBILE-CAPTURE-TM — Phone-Side Capture vs. the Mobile Threat Model

- **Date:** 2026-09-30
- **Status:** DECIDED 2026-09-30 — Option A + sensitive auto-block parity,
  capture toggles stay ON by default. The §8 amendments, the parity gate, and
  the companion doc updates were applied in the same change set; see §10.
- **Standard:** proof-first, user-control-first, local-first, no fake claims.

**The question on the table.** `docs/MOBILE_THREAT_MODEL.md` (2026-09-24)
declares the mobile app free of clipboard monitoring and background clipboard
scraping. The unreleased phone-side capture feature ships a clipboard-change
listener, a foreground watch service, and automatic screenshot import. Those
two facts cannot both be true at the next release tag. This document states
the conflict, documents the surface as actually implemented, and puts three
options on paper so the owner can accept or reject the surface before any
further code moves.

---

## 1. Why now (facts)

| Fact | Evidence |
|---|---|
| The threat model predates all capture code | `docs/MOBILE_THREAT_MODEL.md` last touched in `8e75374` (2026-09-24, the phone-vault tranche). At that point the app had no capture paths at all. |
| Capture shipped after the release cut | `git tag --contains 47c39cb` → none; `git tag --contains 8060d0b` → none. The v0.3.0 tag (`a33483b`) contains neither the capture feature nor the accessibility service. |
| The accessibility attempt is already gone | `8060d0b` added an accessibility auto-capture path; `4386837` reverted it after measurement (§4). `NO_ACCESSIBILITY_SERVICE` in the 2026-09-24 integration report is true again. |
| The released artifact is clean | The download surface serves the signed v0.3.0 APK. Nothing released scrapes anything. |
| The decision window is open | Capture exists only in unreleased master (`47c39cb`, plus `29bdc19`/`0e0e08c`/`0bc5456` test/result commits). Nothing forces a choice until the next release tag. |

## 2. What the current model says (the lines in conflict)

- Product boundary: *"Cache Vault Mobile is **not** cloud sync, account login,
  **background clipboard scraping**, or a remote file manager."*
- Android permissions: *"**Not allowed:** clipboard monitoring, accessibility
  scraping, notification listener scraping."*
- Permissions table: *"Storage/media — **Only** for explicit Save to Phone
  when required."*
- Screenshot rules: *"Save / share: explicit user tap"*; *"No bulk image
  download or silent image library cache."*

A strict reading of those four lines forbids: (a) the clipboard-change
listener, (b) the on-open silent drain, (c) the screenshot auto-import, and
(d) holding `READ_MEDIA_IMAGES` for background observation. The 2026-09-24
integration report makes the same claims per-surface
(`review/CV-ANDROID-SYSTEM-INTEGRATION-20260924/ANDROID_SYSTEM_INTEGRATION_REPORT.md`,
"Clipboard: read occurs only after tapping 'Paste from clipboard'… No
monitor, polling, listener…").

## 3. The capture surface as implemented (measured against source)

| Surface | Trigger | What it reads | Where it writes | User control |
|---|---|---|---|---|
| `ClipboardWatch` listener | Clipboard change while the process is warm | **Nothing.** It never reads clip content; it only posts the "Copied — tap to save" alert (`onChanged`, `ClipboardWatch.kt`) | — | Toggle off; notification permission off; vault lock on → silent |
| `ClipboardSaveActivity` trampoline | User taps that alert or "Save last copy" | Primary clip, only after window focus (platform gate) | Phone-local vault, Default Safe, source `clipboard`/`clipboard_image` | Not exported; every save toasts its result |
| `ResumeDrain` | Any app activity next gains window focus | Primary clip (read is legal only while focused) | Phone-local vault | Toggle; vault lock; 10 s debounce; toast on save |
| `ScreenshotImport` | MediaStore change while capture service runs | New image rows above a watermark, screenshot-like only | Phone-local vault, source `screenshot` | Toggle + photo permission; watermark seeded on first enable so history is never bulk-imported |
| `CaptureWatchService` | Foreground service while anything is enabled | — (keeps process warm) | — | Persistent "Vault capture is on" notification with **Stop capture** action |
| `CaptureBootReceiver` | Device reboot | — | — | Re-arms only if the user left capture on |

Cross-cutting controls in code:

- **Both toggles default ON** (`CaptureStore.kt`) and are exposed in Settings.
- **Vault lock gates everything:** locked → clipboard capture `Skipped("locked")`
  (`ClipboardCapture.kt`); screenshot import returns 0 *without advancing the
  watermark*, so nothing is lost, only deferred (`ScreenshotImport.kt`).
- **Own-copy echo suppression:** 30 s in-memory signature window
  (`ClipboardEcho.kt`) so copying *out* of the vault never loops back in.
- **Dedup:** last-clip SHA-256 signature plus active-item hash check.
- **Sensitive detection:** `SensitiveText` mirrors the desktop detector; items
  are flagged, masked in detail until revealed, and the ledger shows
  "Sensitive item" instead of titles.

## 4. The measured platform ceiling (why the surface is shaped this way)

From `review/CV-VL2-A-HW1-20260929/results_emulator_accessibility.json` and
device logs:

| Scenario | Measured result |
|---|---|
| App focused, clipboard written | `Saved(kind=text)` |
| App backgrounded, write attempted | Platform refuses the write *and* the read |
| Notification tapped | `ClipboardSave: capture result: Saved(kind=text)` |
| Accessibility service variant | Same focus gate; not exempt; reverted (`4386837`) |

The platform states it plainly:

```text
ClipboardService: Denying clipboard access to com.prooffoundry.cachevaultmobile.cvmobile1.debug,
application is not in focus nor is it a system service for user 0
```

Consequence: **no normal app can silently read the clipboard in the
background.** The listener can only *observe that a copy happened* (to post a
notification); the read itself must happen in a focused window — the user's
tap, or the next time the app is opened. That is why the feature is
notification-mediated, and why any claim of "silent background capture" would
be a fake claim.

## 5. Audit against the model's own rules

| Rule | Verdict | Evidence |
|---|---|---|
| "Do not log full clip content / tokens / image bytes" | **PASS** | Logs carry only event kinds and results ("clipboard changed — posting save notification", `resume drain: Skipped(reason=empty)`, "mediastore change: `<row uri>`"); no clip text anywhere in the capture path |
| Ledger: no payloads in activity records | **PASS** | Capture writes source labels (`clipboard`, `screenshot`, `clipboard_image`) and failure-reason labels only; sensitive titles redacted |
| Sensitive masking | **PASS in detail + ledger; list/search masking not audited in this pass** | `LocalItemDetailScreen` masks until reveal; `LocalActivityScreen` shows "Sensitive item" |
| Sensitive auto-block (desktop doctrine: default ON, blocks sensitive auto-capture) | **GAP — no phone parity** | `ClipboardCapture.capture` performs no sensitive check; a copied password is saved (flagged and masked, but persisted) |
| Permissions table current | **STALE regardless of this decision** | Shipped v0.3.0 already uses `USE_BIOMETRIC`, `FOREGROUND_SERVICE(_DATA_SYNC)`, `POST_NOTIFICATIONS`; capture adds `RECEIVE_BOOT_COMPLETED`, `READ_MEDIA_IMAGES`, `READ_MEDIA_VISUAL_USER_SELECTED` |
| Defaults honor "user-control-first" | **DECISION POINT** | Both capture toggles default ON (matches desktop auto-capture default, but is a new always-on-ish surface) |

## 6. Residual risks if the surface is accepted

1. **Sensitive parity gap** (§5): auto-capture saves sensitive-looking clips
   with no block toggle. Recommended hardening: mirror the desktop
   "do not auto-capture sensitive-looking clips" gate, default ON.
2. **Persistent foreground service:** battery/process cost and a permanent
   notification; Android may still kill the process, in which case copies made
   while it is dead produce no alert until the next app open (the drain then
   catches them — nothing is lost, but the alert can be late).
3. **Screenshot heuristic:** conventional `Screenshots` directory /
   `Screenshot`-prefixed names; unusual OEM paths are missed and
   screenshot-named saved images can false-positive.
4. **Partial photo access (Android 14+ "Selected photos"):** with only
   `READ_MEDIA_VISUAL_USER_SELECTED`, unselected rows are invisible and their
   screenshots are silently skipped.
5. **Clipboard image clips:** any image URI on the clipboard saves as a vault
   image on tap — deliberate, but worth knowing.

## 7. Options

### Option A — Accept the surface; amend the model (exact text in §8)
- The threat model is updated deliberately: capture is documented as
  user-invoked or focus-gated, phone-local, toggleable; background reads and
  accessibility/notification-listener scraping stay forbidden.
- Companion updates: superseding note on the 2026-09-24 integration report's
  clipboard row; a phone-capture row in `docs/REPO_TRUTH.md`; the sensitive
  auto-block hardening (§6.1); real-phone smoke of the notification path
  before the next release tag (existing release gate).
- Recommended if the product goal — "copies land in the vault" — stands.

### Option B — Keep the strict posture; cut the feature
- Revert the capture tranche from master (the accessibility service is already
  reverted; nothing of `8060d0b` remains).
- The phone vault keeps: manual "Paste from clipboard", share-to-Cache-Vault,
  bridge browsing. The model's four lines stay true as written.
- CHANGELOG Unreleased capture section is removed; the only doc fix still
  needed is the stale permissions table (biometric/foreground service rows).
- Cost: the product goal dies on the phone; nothing automatic remains.

### Option C — Middle: screenshots automatic, clipboard manual
- Drop the listener, drain, trampoline, and echo machinery; keep
  `ScreenshotImport` and a slimmer watch. Screenshots are the only genuinely
  automatic capture and involve no clipboard at all.
- **This still amends the model:** photo permission for background observation
  contradicts "Storage/media — only for explicit Save to Phone", and
  auto-import needs a phone-side screenshot-rules section. The amendment is
  smaller, not zero.

In every option the bridge threat model, pairing, receipts, and desktop
capture rules are untouched, and the `NO_ACCESSIBILITY_SERVICE` claim stays
true.

## 8. Proposed amendment text (for Option A — approve these words or edit them)

**Product boundary sentence, replaced by:**

> Cache Vault Mobile is **not** cloud sync, account login, or a remote file
> manager. It performs **no background clipboard reads**: the clipboard is
> read only when the user taps a save notification / action, or when an app
> activity gains window focus. Clipboard-change *monitoring* exists solely to
> post that notification; it never reads content while unfocused. Screenshots
> import automatically only while the user has capture enabled. All captured
> content stays in the phone-local vault — no bridge, no network, no cloud.

**"Not allowed" line, replaced by:**

> **Not allowed:** background clipboard reads, accessibility scraping,
> notification listener scraping.

**Permissions table, rows added:**

| Permission | When |
|------------|------|
| Foreground service (dataSync) | Capture watch and bridge connection service |
| Post notifications | Capture and connection alerts (Android 13+) |
| Receive boot completed | Re-arm capture only if the user left it enabled |
| Read media images (+ visual user-selected, Android 14+) | Screenshot import only |

**Threats and mitigations, rows added:**

| Threat | Mitigation |
|--------|------------|
| Capture saves a password to the phone vault | Sensitive detection + masking on reveal; sensitive auto-block toggle (desktop parity, default ON); vault lock pauses capture when locked |
| Capture runs without the user knowing | Toggles in Settings; persistent "Vault capture is on" notification with Stop action; capture defaults documented in the release notes |
| Screenshot import pulls existing photos | Watermark seeded on first enable; only rows newer than the watermark import |
| Captured content leaves the phone | Capture writes only to the phone-local vault; no network involvement; ledger records source labels, never payloads |
| Copies made while the process is dead | On-open focus drain catches them; the alert may be late but nothing is lost silently |

**New section — Phone-side capture rules:**

- Capture destinations: phone-local vault only, Default Safe, source labels
  `clipboard` / `clipboard_image` / `screenshot`.
- Locked vault: clipboard capture skipped with a truthful toast; screenshot
  import deferred (watermark not advanced) — nothing lost, nothing imported.
- No clip content in logs; failure reasons only; sensitive titles redacted in
  the ledger.
- Own copies are echo-suppressed (30 s) and content is deduped by signature
  and active-item hash.
- Enabling screenshot capture never bulk-imports existing history.
- Manual paths (paste, share sheet) work regardless of capture toggles.

## 9. Recommendation

**A**, with the sensitive auto-block parity hardening (§6.1) done before the
next release tag. The surface is already honest: it posts no content in
notifications, reads only in focused windows, writes only to the phone-local
vault, and is toggleable with a visible Stop control. The platform itself
enforces the strongest line in the old model — background reads are
impossible — so the amendment documents reality rather than weakening a real
guarantee. The strict-posture option (B) is the honest alternative if the
"no clipboard monitoring" line matters more than the product goal; C is the
compromise if the listener specifically is the concern.

## 10. Owner decision

- [x] **A** — accept the capture surface; apply §8; add sensitive auto-block parity
- [ ] **B** — keep the strict posture; revert the capture tranche
- [ ] **C** — screenshots automatic only; clipboard stays manual
- [x] Defaults sub-decision: capture toggles stay ON by default

**Decided 2026-09-30 by the owner in review session: Option A + sensitive
auto-block parity (default ON) + toggles stay ON by default.** Applied in the
same change set: the §8 amendments to `docs/MOBILE_THREAT_MODEL.md` (plus the
`Use biometric` permissions row flagged stale in §5), the
`sensitiveBlockEnabled` capture gate with unit tests and a Settings toggle in
both shells, and companion updates (`CHANGELOG.md`, `docs/REPO_TRUTH.md`, and
the supersession addendum on the 2026-09-24 integration report).
