# Cache Vault Android Reconnect QA

Date: 2026-07-01

## Manual device checklist

1. Pair phone to PC from a clean install.
2. Confirm the phone shows the remembered PC and initial `Last seen`.
3. Close and reopen the app.
4. Verify the reconnect approval prompt appears when auto-connect is not yet trusted.
5. Tap `Connect` and confirm the vault loads.
6. Reopen the app and verify `Trust and Connect` enables silent reconnect on later launches.
7. Enable `Keep connected in background`.
8. Background the app and verify the persistent Android notification remains visible.
9. Wait for at least one service poll cycle and verify the notification updates honestly:
   - connected
   - waiting on same Wi-Fi
   - re-pair needed
10. Use the notification action to stop the background connection.
11. Re-enable background mode and force-close the app.
12. Confirm the app does not falsely claim it can reconnect while fully killed.
13. Reopen the app and confirm reconnect resumes.
14. On desktop, revoke the phone.
15. Confirm the phone can no longer reconnect with the old token and surfaces a re-pair path.

## Desktop status checklist

1. Freshly paired but never connected after approval shows `Waiting for phone approval`.
2. Recent live traffic shows `Online`.
3. Stale `last_seen` shows `Offline`.
4. Revoked devices show `Revoked`.

## Evidence to capture after PASS

- Real-device screenshots
- APK filename
- APK SHA256
- Device model + Android version
- Exact desktop build used for QA
