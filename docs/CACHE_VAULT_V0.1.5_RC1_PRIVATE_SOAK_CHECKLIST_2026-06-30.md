# Cache Vault v0.1.5-rc1 — Private Soak Checklist

**Date:** 2026-06-30
**Status:** In Progress — Private Soak Validation

This document defines the checklist and validation flows for testing the **v0.1.5-rc1** release candidate in real-world daily use for **24-48 hours** prior to stable promotion.

---

## Release Candidate Info

| Field | Value |
|---|---|
| **R2 ZIP URL** | `https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip` |
| **R2 SHA URL** | `https://pub-0273ac689b544b959a93bbe5d953d71e.r2.dev/cache-vault/v0.1.5-rc1/CacheVault-v0.1.5-rc1-windows.zip.sha256.txt` |
| **ZIP SHA256** | `31a82ba5c84f31f0faa002f8b02f61c3af0b0ff316cf9458588834c98800e88e` |
| **EXE SHA256** | `1FAEE93F706AEC91A2EE12376C3F83B885CAFF2358E3A88E6C42CB3FB637FFDB` |
| **Git Tag** | `cache-vault-v0.1.5-rc1` |

---

## 24-48 Hour Soak Validation Checklist

Perform the following verification checks during daily usage of the packaged build:

### 1. Selected Paste Workflow
- [ ] **Check:** Select a text/link clip in Cache Vault, right-click, and click `Paste Selected Item`.
- [ ] **Target Apps:** Paste into Notepad, VS Code, Slack, and Chrome.
- [ ] **Verification:** Ensure the correct text is delivered to the foreground target app.
- [ ] **Focus Safety:** Right-click -> `Paste Selected Item` into Cache Vault search bar or settings input. Confirm the delivery skips safely (fails with toast and does not paste).

### 2. Copy-to-Safe Duplication
- [ ] **Check:** Select a text or image clip, right-click, and select `Copy to Safe` -> pick a custom Safe.
- [ ] **Check:** Use the `Copy to Last Safe` shortcut on a subsequent clip.
- [ ] **Verification:** Confirm a duplicate of the clip is created in the chosen destination Safe.
- [ ] **Verification:** Confirm the original clip remains unchanged in the source Safe/inbox.

### 3. Do Not Save Next Copy
- [ ] **Check:** Open the main Control Strip, select `Do Not Save Next Copy`.
- [ ] **Check:** Copy a sensitive string (e.g. password, API token) to the clipboard.
- [ ] **Verification:** Confirm the item is **not** ingested into the Cache Vault database.
- [ ] **Check:** Copy a second string immediately after.
- [ ] **Verification:** Confirm the second string is ingested normally (bypass toggle resets).
- [ ] **Bypass Expiry:** Arm bypass, wait 65 seconds, then copy a string. Confirm it is captured (bypass expired).

### 4. Date & Image UI Polish
- [ ] **Row Timestamps:** Verify list rows display clean, readable timestamps (e.g. `Jun 30, 6:24 PM`) instead of raw ISO format.
- [ ] **Image Previews:** Capture a new screenshot. Confirm the preview renders in the rounded `vault_card` frame.
- [ ] **Image Metadata:** Hover/select the image clip. Confirm filename, dimensions, and size appear correctly.

### 5. Settings Hub & Menu Organization
- [ ] **Context Menu Cascades:** Right-click any clip. Verify submenus (Copy Clean, Organize, Proof, Advanced, Danger) display correctly.
- [ ] **Advanced Labels:** Open Settings. Verify advanced categories (Vault Lock, History, etc.) are prefixed with `Advanced:`.

### 6. Mobile Bridge Default Behavior
- [ ] **Default State:** Fresh install/default profile must confirm Mobile Bridge is OFF by default unless explicitly enabled by the user. No LAN bridge should start silently on first launch.

---

## Soak Test Log (Pass/Fail)

| Flow | Date Tested | Tester | Status (Pass/Fail) | Notes / Defects Found |
|---|---|---|---|---|
| **Browser Download** | 2026-06-30 | User / Agent | **PASS** | R2 ZIP URL opened/downloaded successfully from browser. App launched after extracted/package workflow. Screenshot captured showing Cache Vault v0.1.5-rc1 running during private soak. Proof Foundry /proof was not updated. |
| **Selected Paste** | | | | |
| **Focus Safety** | | | | |
| **Copy-to-Safe** | | | | |
| **Do Not Save** | | | | |
| **UI Polish** | | | | |
| **Menu Honesty** | | | | |
| **Mobile Bridge Default**| | | | |
| **System Stability** | | | | |

---

## Final Verdict & Promotion Recommendation

- **Verdict:** **PENDING SOAK TEST**
- **Recommendation:** **HOLD** (Maintain unlisted RC status until soak window completes)
