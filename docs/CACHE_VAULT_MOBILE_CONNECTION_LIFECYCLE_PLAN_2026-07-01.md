# Cache Vault Mobile Connection Lifecycle Plan

Date: 2026-07-01

## Scope

This lane covers the Android companion/APK only. It does not change desktop packaging, publish a new desktop artifact, or touch `/proof`.

## Product behavior

1. Pairing persists on both sides.
2. The phone remembers the trusted PC identity, host, port, and last successful contact time.
3. When the app opens, it attempts to rediscover the trusted PC on the same Wi-Fi.
4. If silent reconnect is not trusted yet, the phone shows an approval prompt:
   "Connect to this PC?" with `Connect` and `Not now`.
5. If the user opts into trusted auto-connect, the app reconnects silently on future launches.
6. `Keep connected in background` is opt-in only and uses an Android foreground service plus a persistent notification.
7. If the app is force-closed, reconnect resumes when the user opens the app again. The app must not falsely claim it can wake itself from a killed state.

## Implemented code path

- Android pairing state now stores:
  - PC label
  - last seen timestamp
  - auto-connect approval
  - background keep-connected preference
- Android foreground service:
  - polls for the trusted PC on LAN
  - updates persistent notification state
  - attempts silent reconnect only when the user previously approved it
- Desktop paired-device list now distinguishes:
  - Waiting for phone approval
  - Online
  - Offline
  - Revoked

## Known limitations

- mDNS/LAN discovery still depends on the local network allowing discovery.
- There is still no shipped QR scan flow in this patch.
- A fully killed Android app cannot be reliably reawakened by the PC without a push or platform-specific wake channel.
- Manual device QA is still required before claiming reconnect reliability on real hardware.

## Release gate

Before publishing a new APK:

1. Build the fresh APK.
2. Install on a real Android device.
3. Verify reconnect prompt flow.
4. Verify background keep-connected notification and stop action.
5. Revoke the device on desktop and confirm old token rejection.
6. Capture screenshots and APK SHA256 after QA passes.
