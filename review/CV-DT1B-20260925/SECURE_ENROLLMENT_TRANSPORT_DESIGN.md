# CV-DT1B — Secure Enrollment and Transport Design

**Status:** READ-ONLY design complete; implementation not authorized.
**Product source mutation:** NO. The 13-file CV-VL2-A candidate was not edited.
**Source identity before this audit:** `2be78242c3634278825ba33d610840a44c11eee5684a21ec5f667a53fe3b9877`.

## Recommendation

Use **mutual TLS (B), with an explicitly pinned local server CA and one-time owner-approved enrollment**. Mutual TLS is the smallest option here that actually separates an enrolled device identity from a replaceable session credential: the Android private key authenticates the device, while a short-lived opaque credential carries the current server-side session and scopes. TLS server pinning alone (A) closes passive observation and server impersonation, but a stolen client bearer remains replayable and the device has no cryptographic identity of its own.

Keep the existing Mobile Bridge routes where their behavior is safe, but move them to protocol 2, require TLS and a client certificate, make the existing temporary offer mandatory, and enforce a server-side scope per route. No HTTP fallback is allowed. Discovery remains address discovery only.

This design has two compatibility questions that must be answered in isolated `PROTOTYPE_ONLY` work before product edits: (1) AndroidKeyStore private-key/certificate-chain association with the existing OkHttp client on the supported API range, and (2) Windows Python TLS loading of the leaf certificate without leaving a plaintext long-term private key on disk. These are implementation gates, not reasons to weaken the design silently.

## Current implementation constraints

| Area | Current source evidence | Consequence |
|---|---|---|
| Windows HTTP stack | `http.server.ThreadingHTTPServer` and `BaseHTTPRequestHandler` in `cache_vault/core/mobile/bridge.py`; no TLS context is installed. | Python's standard `ssl` can wrap accepted sockets and verify client certificates. The current request handler will need its authenticated peer certificate mapped to a device before dispatch. |
| Android HTTP stack | OkHttp 4.12.0 in `android/app/build.gradle.kts`; `BridgeClient` constructs `http://` URLs and uses default platform TLS settings only when given HTTPS. | Keep OkHttp; provide a per-pairing TLS context/trust anchor and AndroidKeyStore-backed client key manager. No separate HTTP library is needed. |
| Python and packaging | Active interpreter Python 3.13.2; project declares Python `>=3.10`; `cryptography>=42.0.0`, conditional `pywin32>=306`, and PyInstaller `>=6.0` are already declared. The PyInstaller spec already includes `cryptography` and `cache_vault.core.mobile.*` hidden imports. | Certificate issuance can use existing `cryptography`; Windows DPAPI is available through Windows APIs/pywin32. No new Python package is proposed. A frozen-package smoke remains required. |
| Android build | `minSdk=26`, `targetSdk=34`, `compileSdk=34`, Java/Kotlin target 17, AGP 8.5.2, Kotlin 1.9.24. | AndroidKeyStore and `KeyGenParameterSpec` are available above the app's minimum API. Test at API 26 and a current Android release. |
| Existing crypto/storage | Python `ssl` and `cryptography` are present; no current product call to DPAPI, Credential Manager, or CNG was found. Android has OkHttp, JCA, AndroidKeyStore, `androidx.security:security-crypto:1.1.0-alpha06`, and `androidx.biometric:biometric:1.1.0`. `PairingStore` uses EncryptedSharedPreferences; `VaultLockStore` already demonstrates direct AndroidKeyStore AES/GCM use. | Reuse platform APIs. Do not put private keys in Windows `settings.json` or Android ordinary preferences. `EncryptedSharedPreferences` is deprecated in Security Crypto 1.1.0; use the platform Keystore primitive directly for new credential wrapping. |
| Current discovery | Windows advertises `_cachevault._tcp.local.` with product name and PC hostname TXT properties; Android `PcDiscovery` resolves an IPv4 address and returns it with service name/port. | mDNS can remain a route hint. It must not identify, enroll, authenticate, or authorize a device. TLS identity must be checked after discovery. |
| Current bridge default | Port 8742; blank bind setting resolves to `0.0.0.0`. | Default the listener to the selected reachable private-LAN address set, not every IPv4 interface; explicit owner settings may select a supported local interface. Do not publish the CA pin or offer secret through mDNS. |
| Current lock behavior | The re-baselined candidate checks Mobile Access enabled and Vault Lock state before route dispatch; locked bridge requests, including pairing, return 423. | Preserve the CV-VL2-A rule. TLS handshake success and client authentication never override Vault Lock. |

### Proven bootstrap and credential facts

- `PairingOfferManager` already generates 32 bytes of URL-safe randomness and sets a 300-second expiry. The QR contains host, port, token, version, expiry, and PC label. Offers live in process memory and are single-use in the normal sequential path.
- The offer is **optional at the server endpoint**: `_dispatch_public_pair_post` consumes it only when a token is supplied. Android's discovered-PC flow calls `pairDevice` without a token; Windows therefore accepts discovered pairing while Mobile Access is enabled. The offer manager has no lock around consume, so simultaneous replay also needs an atomic single-use check.
- The owner-facing QR dialog creates an offer when its QR is generated. The public pair endpoint has no separate owner-approval state after the QR is displayed.
- After pairing, Windows generates a separate 32-byte device bearer and stores its SHA-256 verifier in the `paired_devices` array in `settings.json`. That bearer has no expiry. The Android app stores host, port, caller/server-provided device ID, and plaintext bearer inside EncryptedSharedPreferences. The bearer is sent in `Authorization` on every request over HTTP.
- `device_id` is caller-supplied when present (and an existing ID can replace the matching record). It is not a cryptographic identity. The server-generated bearer is not currently a separate session record, and scopes do not exist.
- The mobile receipt log records route/action/result, device metadata, clip ID, reason, and remote IP; it does not need secrets or request bodies. Reuse it for safe lifecycle events, never for offers, private keys, CSR private material, session tokens, or raw authorization headers.

## Architecture comparison

| Design | SECURITY_GAIN | NEW_DEPENDENCIES | WINDOWS_COMPLEXITY | ANDROID_COMPLEXITY | PACKAGING_RISK | MIGRATION_COST | REVOCATION_QUALITY | LOCAL_FIRST_COMPATIBILITY | FAILURE_MODES |
|---|---|---|---|---|---|---|---|---|---|
| **A. HTTPS, local server identity, Android pin** | Encrypts requests and authenticates the PC after the user pins its local identity. With a mandatory offer and owner approval it closes unauthenticated enrollment. A stolen client bearer remains replayable until it expires or is revoked; there is no client public-key identity. | No new runtime dependency: Python `ssl`/`cryptography`, existing OkHttp/JCA. Windows key protection uses existing OS DPAPI APIs. | Medium: create a local CA/server identity, protect its key, issue/rotate server leaf certificates, bind to reachable addresses, and load TLS material. | Medium: pair-specific trust anchor/pin, host verification, pin rotation and credential persistence. | Medium: verify frozen `cryptography`/pywin32 imports; certificate files and key lifecycle must survive PyInstaller. | Medium: require updated Android app and re-pair every legacy device; scope and token migration still needed. | Good for new requests if session verifiers are checked per request; revocation cannot retract bytes already returned. Bearer theft remains a residual. | Excellent: self-hosted local CA and LAN/mDNS; no cloud or public CA. | Lost/reset Windows DPAPI state, CA rotation without a prepared backup pin, IP/SAN mismatch, untrusted fallback, stolen bearer, certificate expiry. |
| **B. Mutual TLS (selected; includes A's pinned server identity)** | Authenticates both endpoints. Android's private key proves device identity; the separately rotated session credential can carry short-lived scopes and is insufficient by itself without the client key. Strongest fit for the stated identity/session separation. | No Android crypto dependency required: JCA/AndroidKeyStore and OkHttp. Existing Python `cryptography`, `ssl`, and Windows DPAPI APIs suffice for a software CA. TPM/CNG integration is optional and would require separate compatibility proof. | High: local CA/leaf issuance, Windows key custody, peer-certificate extraction, certificate-to-device mapping, session issuance, revocation and TLS connection closure. Python's `ssl` API takes certificate/key file paths; the private-key loading path must be proven safe. | High: generate a P-256 identity key in AndroidKeyStore, associate the returned certificate chain, configure OkHttp client-auth, and test vendor/API behavior and reinstall/key invalidation. | Medium-high: PyInstaller must carry `cryptography` and Windows API bindings; no private identity key may be shipped as an ordinary resource. | High but truthful: all legacy devices re-enroll; HTTP/protocol 1 is disabled; credentials/scopes are newly issued. | Strong: block new handshakes and requests by certificate/device state, invalidate all session credentials, close active connections where possible. In-flight response data already sent cannot be recalled. | Excellent: local CA and mDNS only; no hosted PKI. | CA loss/DPAPI failure, Android Keystore key invalidation, cert chain import failure, client-auth handshake failure, stale clock, missed revocation check, rollback to old HTTP. |
| **C. Application-layer signed requests over TLS** | Can add proof-of-possession and replay controls, but duplicates what mTLS already provides for this point-to-point app. | Existing primitives exist, but correct nonce/canonicalization/replay/session code is not an existing dependency. A standard protocol and maintained implementation would be needed. | High: signature format, key mapping, replay cache, nonce lifecycle, error semantics. | High: request signing, concurrency/retry handling, persistent nonce state. | Medium-high: signing library/hook packaging and protocol test surface. | High: every route/client must adopt the new signing protocol. | Potentially good only with robust replay windows and revocation checks. | Excellent in theory. | Canonicalization bugs, replay races, clock assumptions, retry mismatch. Do not create a custom cryptographic protocol. |
| **D. Existing bearer model over TLS only** | Hides bearer and content from passive observers and can authenticate the PC if pinned. It does not close tokenless enrollment, bind an independent device key, limit authority, or stop replay of a stolen bearer. | None beyond A. | Low-medium. | Low-medium. | Low-medium. | Low for transport, but still needs forced re-pair or offer enforcement to repair bootstrap. | Existing per-request revocation remains useful; stolen token can be replayed until revoked. | Excellent. | Optional pairing offer remains a bypass; static bearer theft, broad authority, no cryptographic device identity. |

**Selection:** B. A is the shortest transport patch, but it does not fully solve the identified device-identity/session collision. B reuses the existing Python/Android stacks and native key stores while accepting a larger, testable re-enrollment. C is rejected as unnecessary protocol invention. D is not an acceptable target or compatibility fallback.

## Target pairing ceremony

1. The owner explicitly opens the existing desktop Pair Device/QR flow. Only this action creates a pending offer; Mobile Access enabled by itself is not enrollment authorization.
2. Windows creates a random public `offer_id` and a separate 256-bit secret `offer_secret`, retains only a verifier for the secret, and gives the offer a 120-second server-enforced lifetime. Offers expire on process restart and are consumed atomically exactly once. Keep the secret out of logs, receipts, settings, analytics, and clipboard history; QR copy remains an explicit secret disclosure.
3. The QR carries public metadata: protocol version 2, endpoint/port, offer ID, UTC expiry for display, the local CA certificate and its SHA-256 fingerprint, and the owner's scope ceiling. It carries the one-time offer secret as secret material. The public CA certificate/fingerprint authenticate the Windows endpoint; mDNS data does not.
4. After validating the CA trust anchor, Android generates a non-exportable P-256 key in AndroidKeyStore and submits its public-key CSR, display name/platform/model, requested capabilities, and the one-time offer secret over HTTPS. The client never sends a private key. The phone-supplied device name and requested scopes are untrusted claims until shown to the owner.
5. Windows consumes the offer once, validates protocol/expiry, creates a pending enrollment, and asks the owner to approve the displayed device and requested scopes in the existing pairing surface. A copied QR alone cannot silently register an active device. Deny, expiry, lock, or disable invalidates the pending offer/request.
6. On approval, Windows assigns a fresh `device_id`, binds the submitted public-key fingerprint, issues a client certificate, records owner-granted scopes, and returns the certificate chain. Android associates that chain with the same AndroidKeyStore private key. Android reconnects with mTLS; only then does the server issue a short-lived opaque session credential.

Offer fields are not capabilities themselves. The phone's requested scopes are a request, never an authorization. The owner grants a subset of the offer ceiling; the server intersects that grant with route policy on every request.

## Identity, credential, and session records

| Record | Target fields and ownership | Current-source mapping |
|---|---|---|
| `TrustedDevice` | `device_id` (server generated), `display_name`, `platform`, `identity_spki_sha256`, `certificate_serial`, `created_at`, `last_seen_at`, `revoked_at`, `trust_state`, `granted_scopes[]`, `background_reconnect_allowed`, `protocol_version`. The public key/certificate fingerprint is the stable identity; the ID is a public handle, never a token. | `PairedDevice.device_id`, `device_name`, `platform`, `created_at`, `last_seen_at`, `revoked_at`, and `protocol` can be mapped. Public-key fingerprint, cert serial, trust state, and scopes require migration/new storage. Existing `device_id` values are not promoted as cryptographic identity. |
| `PairingOffer` | `offer_id`, `offer_secret_verifier`, `created_at`, `expires_at`, `state`, `server_ca_key_id`, `scope_ceiling`, optional pending request ID. Volatile/in-memory; secret never persisted. | Current `PairingOffer` has token/host/port/times/PC name/consumed. It needs ID/verifier, CA identity, synchronized single-use transition, owner-approval state, scope ceiling. |
| `SessionCredential` | `credential_id`, `device_id`, `secret_hash`, `created_at`, `expires_at`, `revoked_at`, `granted_scopes_snapshot`, `rotated_from_id`. Raw token is returned once over mTLS and stored only in Android Keystore-wrapped local storage. A credential alone cannot authenticate without matching client certificate. | Current `token_hash` is a field inside `PairedDevice`; split to a credential record, add expiry/rotation and require the matching mTLS device. |
| `ActiveSession` | Volatile `session_id`, `device_id`, `credential_id`, TLS connection identity, `started_at`, `last_seen_at`, `closed_at`, scope snapshot. Lost on process restart; close on revoke, lock, disable, expiry, or device cert change. | No explicit session table exists; each request currently checks a static bearer. This record and connection map are new. |

The trust store may persist public device metadata, certificate serials/fingerprints, scope grants, credential hashes, and revocation history. It must not put the CA private key or device private key in `settings.json`. Keep the Windows CA private key in a separate DPAPI-protected, current-user blob. Android identity keys remain non-exportable in AndroidKeyStore. Session tokens are protected with a non-exportable AndroidKeyStore AES key; the current encrypted preference library is not the new key API.

## Route authorization and Vault Lock

The complete current route-to-scope table is `CURRENT_TO_TARGET_ROUTE_MATRIX.csv`. Default to deny and use these scope meanings:

- `BROWSE_LOCAL_SUMMARIES`: list/search/collection/inbox summaries, excluding sensitive and Safe content until an explicit higher scope exists.
- `REQUEST_ITEM_DETAIL`: one clip's full content or image asset, subject to policy; it does not imply sensitive/Safe access.
- `SEND_TO_DEVICE`: Windows-to-Android content delivery. No current route implements this capability; grant none in tranche 1.
- `RECEIVE_FROM_DEVICE`: Android-to-Windows `/mobile/v1/inbox/send` only.
- `BACKGROUND_RECONNECT`: a separate owner-approved Android background permission; it does not imply browse/detail/receive scope. It permits the background service's status/reconnect operation only.
- `VIEW_SENSITIVE`, `EXPORT`, `MANAGE_SAFES`, `DELETE`, `RESTORE`, and `SETTINGS`: no current route needs them; they are denied/not issued in tranche 1.

For a protected request all checks are independent and ordered before content dispatch: Mobile Access enabled, Vault Lock currently permits access, valid server-authenticated TLS channel, valid client certificate mapped to an active `TrustedDevice`, valid unexpired `SessionCredential` bound to that device, and the exact route scope. Pairing is subject to the same enabled/lock policy and additionally requires a live offer and owner approval. TLS/client identity never unlocks the vault.

Revocation re-reads device/session state per request, invalidates every session credential for the device, closes registered connections, rejects future TLS handshakes/requests, and marks offers/pending enrollments for that identity invalid. Recheck policy before sending protected response bytes where practical. A response already delivered and content copied off-device cannot be recalled. A request admitted before a lock/disable transition may have work in flight; do not claim retroactive erasure.

### Lock and bridge event semantics

Keep the lock event vocabulary from `CV-VAULT-LOCK-2/RECONCILIATION.md` unchanged: `vault.locked`, `vault.unlocked`, `vault.unlock_failed`, and `vault.lock_settings_changed`. Mobile transport does not create a second lock authority or a second spelling for those transitions. A `vault.locked` transition closes active bridge sessions/connections and prevents pairing or protected responses; an authenticated request rejected by the lock continues to use the existing mobile receipt result/reason (`denied` / `vault_locked`) rather than emitting a fresh `vault.locked` transition per request. Authentication, certificate issuance, session renewal, and successful route authorization are not unlock events. Only the Vault Lock authority records `vault.unlocked` after its accepted authenticator transition. Preserve the canonical safe lock-event fields and never add PIN/passphrase, verifier, salt, biometric canary, private key, offer secret, session token, raw authorization header, or raw authentication exception to either event or receipt records.

## Key custody and rotation

| Key | Windows | Android |
|---|---|---|
| Local CA signing key | Generate with existing `cryptography`; protect its private serialization with current-user DPAPI through Windows APIs/pywin32; keep only the encrypted blob at rest outside ordinary settings. Decrypt only in memory for issuance. Windows CNG/Platform Crypto Provider is the stronger non-exportable TPM option, but Python's current `ssl`/OpenSSL path has no proven CNG handle integration; do not claim TPM backing without a prototype. | Not held here. |
| Server TLS leaf key | Generate per process in memory and sign with local CA. Python `SSLContext.load_cert_chain()` currently accepts certificate/key file paths, so a narrowly scoped owner-only temporary PEM is a potential integration bridge. It must be securely ACLed, deleted immediately after context load, and tested for crash residue. If this cannot be justified, use a TLS adapter that can consume in-memory keys or a Windows-native TLS provider; do not persist plaintext CA/server keys. | Trust the pinned local CA obtained from the intentional QR; use normal TLS certificate-chain and endpoint-name/IP validation. Keep current/next CA fingerprints during planned rotation. |
| Device identity key | No Windows device private key for Android identities. Public device keys/certificates and serials can be in the trust store. | Generate P-256 in `AndroidKeyStore` using `KeyGenParameterSpec`; private key never enters preferences or leaves the key store. Associate the CA-signed client certificate chain with that key. StrongBox may be used when available, never required for pairing. |
| Session wrapping key | No client session token stored here; Windows stores only high-entropy token hashes. | A non-exportable AndroidKeyStore AES-GCM key wraps the raw session token in app-private storage. `allowBackup=false` already prevents app backup. On reinstall/key loss, require explicit re-enrollment. |

Server leaf rotation can retain the same CA and does not require re-pairing; regenerate the leaf when local addresses change and include the current address SANs. CA/root rotation requires an authenticated overlapping old/new root update or explicit owner-led re-pair. Android client key rotation requires a valid old mTLS identity or a fresh QR enrollment; revoke the old serial and its sessions. A Windows DPAPI reset/machine/profile migration that loses the CA key fails closed and requires re-pairing.

## Protocol and first implementation tranche

```ini
TRANCHE_NAME = CV-DT1B-1 — PINNED LOCAL mTLS ENROLLMENT AND SCOPED SESSIONS
PROTOCOL_VERSION = 1 -> 2
MOBILE_API_VERSION = "1" -> "2"
LEGACY_HTTP_FALLBACK = DISABLED
```

The current compatibility window is protocol 1 only. Protocol 2 becomes the only accepted bridge protocol when the tranche is enabled. Keep the existing route paths unless a compatibility test requires a versioned path; reject protocol 1 and cleartext outright rather than routing it to a reduced-security side door.

Exact expected implementation files and tests are listed in `MIGRATION_PLAN.md`. Do not start product implementation until the two key-handling/Android mTLS PoCs pass. This is a design recommendation, not implementation authorization.

## Official platform references

- Python TLS context and certificate loading: [Python `ssl`](https://docs.python.org/3.13/library/ssl.html#ssl.SSLContext.load_cert_chain).
- Android custom trust anchors, pinning, and cleartext policy: [Network Security Configuration](https://developer.android.com/privacy-and-security/security-config).
- Android non-exportable key material and hardware-backed key options: [Android Keystore system](https://developer.android.com/privacy-and-security/keystore).
- Android key-pair generation and certificate association: [KeyGenParameterSpec](https://developer.android.com/reference/android/security/keystore/KeyGenParameterSpec).
- Existing EncryptedSharedPreferences API deprecation and direct platform-API direction: [AndroidX Security Crypto release notes](https://developer.android.com/jetpack/androidx/releases/security) and [EncryptedSharedPreferences API](https://developer.android.com/reference/androidx/security/crypto/EncryptedSharedPreferences).
- Current-user Windows key protection: [CryptProtectData](https://learn.microsoft.com/en-us/windows/win32/api/dpapi/nf-dpapi-cryptprotectdata).
- Windows non-exportable/TPM-capable CNG provider options: [CNG Key Storage Providers](https://learn.microsoft.com/en-us/windows/win32/seccertenroll/cng-key-storage-providers).

```ini
CURRENT_TRANSPORT = cleartext HTTP + device bearer; default listener 0.0.0.0:8742
TARGET_TRANSPORT = TLS 1.2+ with local CA trust + mutual TLS client identity + scoped session credential
PAIRING_BOOTSTRAP = explicit 120-second, 256-bit, single-use QR offer + server CA pin + owner approval
DEVICE_IDENTITY_MODEL = server-assigned device_id bound to AndroidKeyStore public key/certificate fingerprint
SESSION_CREDENTIAL_MODEL = short-lived opaque random token, stored as hash server-side, AndroidKeyStore-wrapped, usable only with matching client certificate
REVOCATION_MODEL = device/certificate allow-list check per request + invalidate all session tokens + close active TLS sessions; preserve local data/audit history
LEGACY_MIGRATION = mark all v1 rows LEGACY_PAIRED and reject them; require new protocol-2 enrollment; no automatic trust promotion or HTTP fallback
FIRST_IMPLEMENTATION_TRANCHE = CV-DT1B-1 — PINNED LOCAL mTLS ENROLLMENT AND SCOPED SESSIONS
CV_DT1B = COMPLETE
PRODUCT_SOURCE_CHANGED = NO
COMMIT = NO
PUSH = NO
```
