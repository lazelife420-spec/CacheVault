# Do Not Save Next Copy GUI QA Receipt — 2026-06-30

## Commit Tested
`6b58dc89c43cd6971a185e6dc271ed7a302d6f04` (with Temporary Clipboard Bypass implementation)

---

## Flows Verified & Pass/Fail Status

| Flow | Description | Expected Behavior | Actual Behavior | Status |
|---|---|---|---|---|
| **1. UI Action Label** | Select "Do Not Save Next Copy" from OptionMenu | Dropdown shows label "Do Not Save Next Copy" and arms skip-next state. | OptionMenu dropdown text and mapping updated to "Do Not Save Next Copy". | **PASS** |
| **2. Armed Status Feedback** | Visible status feedback when armed | Label of the OptionMenu displays "Next copy will not be saved" when armed. | OptionMenu text updates instantly to "Next copy will not be saved". | **PASS** |
| **3. Intercept & Skip** | Copy text A externally after arming | Clipboard monitors change event but skips saving it to DB. Shows "Copy skipped" Toast. | Ingestion skips saving and shows "Copy skipped" Toast successfully. | **PASS** |
| **4. Expiry / Cancellation** | Expiration safety timeout check | Arming expires after 60 seconds; status reverts back to normal. | Status reverts safely back to "Capture: On" upon expiration (via check timer). | **PASS** |
| **5. Subsequence Normal Capture**| Copy text B after bypass consumed | Capture resumes automatically and saves text B normally. | Re-enables capture and inserts text B normally in database. | **PASS** |
| **6. Local Audit Receipts** | Ignored receipt log event | Adds a local audit event when a clipboard copy is bypassed. | Records EVENT_CLIPBOARD_NEXT_COPY_IGNORED event and generates ignored receipts. | **PASS** |

---

## Visual Verification Screenshot
The following screenshot verifies that the OptionMenu status label dynamically updates to `"Next copy will not be saved"` when the user arms the temporary clipboard bypass workflow:

![Do Not Save Next Copy GUI](../visual_smoke/do_not_save_next_copy_workflow.png)

---

## Technical & Security Caveats
1. **Local-Only Bypassing:** When armed, the next clipboard update event is ingested by the background listener to consume the arming trigger, but the payload content is explicitly discarded and never written to the SQLite database or disk files.
2. **Audit Accountability:** To align with Proof/Audit design expectations, a local-only `EVENT_CLIPBOARD_NEXT_COPY_IGNORED` receipt event is written to the local event registry (excluding content bytes or hashes) to document that a user-commanded bypass operation was executed.

---

## Verification Commands Run
1. **Automated GUI test suite runner:**
   ```powershell
   python scripts/verify_do_not_save_gui.py
   ```
   *Result:* **PASS** (verified OptionMenu text transitions, bypass consumption, auto-resume capture, and saved screenshot)

2. **Full test suite execution:**
   ```powershell
   pytest -p no:xonsh
   ```
   *Result:* **754 passed**

3. **Compilation verification:**
   ```powershell
   python -m compileall cache_vault
   ```
   *Result:* **PASS**

4. **Self-test run:**
   ```powershell
   python app.py --selftest
   ```
   *Result:* **PASS** (returned `selftest OK`)

---

## Final Verdict
**GREEN / RELEASE-READY**
Temporary clipboard bypass, status tracking, automatic expiration, and user notifications are fully verified and stable on Windows 10/11.
