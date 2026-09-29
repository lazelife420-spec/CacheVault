# CV-DT1A — Current Mobile Bridge / Trust Boundary Audit

**Date:** 2026-09-25  
**Mode:** Read-only source and test review  
**Source edits:** None  
**Tests:** Not run  
**Commit / push:** None

## Disposition

The desktop is the HTTP server and Android is the client. The current bridge is plain HTTP on IPv4, defaults to all IPv4 interfaces on port 8742, and advertises the service through mDNS while enabled. The client sends a reusable bearer token in an HTTP header. The Android app explicitly permits cleartext traffic.

The strongest current boundary defect is more direct than token transport: POST /mobile/v1/pair-device is unauthenticated and accepts a request without a pairing offer. Android’s discovered-PC flow uses that no-offer path. The server test test_public_pair_device_returns_token_without_logging_plaintext intentionally asserts it succeeds without a pairing token. A reachable LAN peer can therefore enroll itself while Mobile Access is enabled and the Vault Lock gate is open. A caller-supplied existing device_id replaces that device’s current credential record.

After pairing, an active device has broad all-or-nothing access: protected read routes include clip previews, full clip detail and image assets across the vault; the same bearer can also POST mobile content into the desktop inbox. There are no per-device or per-action scopes. The Android background-reconnect preference controls client behavior only.

The uncommitted CV-VL2-A candidate adds a centralized lock-state check before route dispatch. This check covers pairing and all requests processed by MobileBridge.handle; it is candidate-only evidence. It does not cancel a handler already past the check, and no physical lock/runtime behavior was exercised in this audit.

## Evidence labels

- **PROVEN_CURRENT** — directly present in current source or asserted by a test’s source. No test execution is implied.
- **CV_VL2_A_CANDIDATE_ONLY** — present in the frozen, uncommitted Vault Lock candidate, not in the base commit.
- **HISTORICAL** — older or retained behavior/evidence; not sufficient to establish current runtime behavior.
- **PLANNED** — proposed architecture or work, not implemented.
- **UNKNOWN** — not established from the reviewed source/test surface.
## Current versus historical/planned claims

- **HISTORICAL / stale description:** the API module and settings comments call Mobile Access read-only, but current source includes authenticated POST /mobile/v1/inbox/send, which writes vault content. The comment is not an authorization boundary.
- **PLANNED:** the proposed TrustedDevice/scopes boundary and the CV-DT1B-1 tranche below are future architecture only; no such scope or independent device-key identity is present in current code.
- No historical audit assertion was used as proof of current transport, pairing, or lock behavior. Findings above come from current source and test definitions. The stale read-only descriptions appear in C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\api.py line 1 and C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\settings.py lines 74–79.

## 1. Transport topology

| Property | Finding | Classification |
|---|---|---|
| Roles | Windows MobileBridge accepts requests; Android BridgeClient sends them. Windows CLI has a separate HTTP client path as well. | PROVEN_CURRENT |
| Protocol | ThreadingHTTPServer and Android URLs use http://. No TLS wrapping, HTTPS listener, WebSocket endpoint, or certificate pinning was found in the reviewed bridge/client code. | PROVEN_CURRENT |
| Bind and port | Empty mobile_access_bind_host resolves to 0.0.0.0; the default port is 8742. A configured host/port overrides these values. | PROVEN_CURRENT |
| LAN and loopback | Default 0.0.0.0 binds all IPv4 interfaces, including loopback. A loopback-only bind is configurable, but is not the default. | PROVEN_CURRENT |
| Discovery | _cachevault._tcp.local. mDNS is advertised while enabled, with a desktop label/name, IPv4 address(es), and port. It is discovery metadata, not authenticated server identity. | PROVEN_CURRENT |
| Pairing changes exposure | Pairing does not change the listener bind or port. Enabling Mobile Access starts the listener and discovery; pairing adds a device record. | PROVEN_CURRENT |
| Firewall rules | No in-repository bridge/firewall-rule creation call was found in the reviewed product source. Whether Windows Defender Firewall or another host/network policy permits the listener is environment-dependent. | UNKNOWN |
| Disabled state | The controller stops mDNS and the listener and persists disabled state. The handler also returns 503 and stops a stray listener if directly reached while the setting is disabled. Existing pairing records are retained. An already accepted request is not explicitly cancelled. | PROVEN_CURRENT |

The server’s standard handler suppresses its HTTP access-log callback. The POST handler rejects bodies over 20 MiB before dispatch; ordinary bridge routes then enter handle. HEAD and OPTIONS are not implemented by this handler and fall through to the base handler’s non-dispatch response path; no protected route body or operation is exposed by that path.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 91–115, 117–155, 157–248; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\models.py lines 13–20; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\mobile_access_controller.py lines 131–220; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\discovery.py lines 17–71, 96–124; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 111–141, 192–204, 254–262; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\AndroidManifest.xml lines 14–22.

## 2. Pairing bootstrap and credential lifecycle

There are two materially different paths.

### QR offer path

1. The Windows pairing dialog creates a pairing offer and displays/copies its QR payload.
2. The offer contains host, port, a 32-byte-entropy URL-safe token, expiry, and PC name. It is held in the in-memory PairingOfferManager; the offer TTL is 300 seconds.
3. Android parses host, port, and token from the scanned payload and POSTs them to /mobile/v1/pair-device over HTTP.
4. If the server receives a non-empty offer token, it consumes it and rejects an expired or previously consumed token. Consumption is in-memory and has no explicit synchronization around the check-and-set; concurrent-consumer behavior is therefore UNKNOWN from source review.
5. The server then creates a separate 32-byte-entropy device bearer token, stores its SHA-256 hash with the device record, and returns the plaintext bearer once in the HTTP JSON response.
6. Android stores the bearer in encrypted shared preferences.

The offer is single-use only when it is supplied. The route accepts an empty or absent offer token and proceeds to issue a device bearer. The Android discovered-PC flow calls pairDevice() without a token; the desktop does not approve that request separately. The user taps Connect on Android, but that is not Windows-side approval.

### Manual code path

The Windows dialog also has Generate Fresh Pairing Code, Show Token, Copy Token, and Copy All Setup Info. This path calls the local Windows pair_device method, creates the permanent device bearer directly, and presents it for manual setup. That bearer has no expiry field or rotation schedule. It remains usable until device revocation or replacement. Copying setup information or the QR payload puts the relevant credential material on the clipboard.

### Credential properties

| Credential | Entropy / format | Lifetime / replay | Persistence |
|---|---|---|---|
| Pairing offer | 32 random bytes via secrets.token_urlsafe(32) | Five minutes; one-time sequential consume when supplied. Absent token bypasses offer validation. Concurrent consume is not synchronized. | Windows process memory; QR payload/copy is visible to anyone who can read that display/clipboard. |
| Device bearer | 32 random bytes via secrets.token_urlsafe(32) | Reusable; no expiry enforcement. Each accepted request can replay while the device is active, Mobile Access is enabled, and lock policy permits it. | Windows stores SHA-256 verifier in paired-device settings. Android stores bearer using EncryptedSharedPreferences backed by an AES-256-GCM master key. |
| Windows manual code | Same device bearer | No expiry; revocation/re-pair is the invalidation mechanism. | Plaintext displayed/copied on demand; only its hash is stored in the Windows paired-device record. |

The Windows settings store is JSON at %LOCALAPPDATA%\CacheVault\settings.json; the audit inspected source only and did not open the live file. The stored server-side verifier is a hash, not the plaintext bearer. Android’s manifest disables Android backup (allowBackup=false); no actual device preferences or Android logs were read.

**Replay/idempotency:** there is no request nonce, timestamp, or idempotency key in the Bridge request model. GETs are repeatable. Copy/share/save POSTs can create repeated receipts. Repeating /inbox/send can create another mobile capture; the receive path has no request deduplication key. Repeating a no-offer pairing request mints another credential or, with the same caller-supplied ID, replaces the existing record. A supplied offer token rejects later sequential replays, but not the no-token path.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\pairing_offer.py lines 14–46, 60–115; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 251–279, 691–735; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\models.py lines 40–89; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\settings.py lines 17–19, 245–250; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\ui\mobile_dialogs.py lines 102–136, 239–280, 331–422; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeRepository.kt lines 72–140; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\PairingStore.kt lines 7–64, 85–99; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 111–141.
## 3. Device identity

**DEVICE_IDENTITY_SEPARATE_FROM_TOKEN = PARTIAL**

A paired record has a separate device_id, display name, created/last-seen/revoked timestamps, platform, app/protocol version, model, and build. Android generates a random UUID-derived identifier and reuses it during re-pair while it remains in local storage. The device ID is not a credential: the server accepts it from the request, and authenticates by matching the supplied ID and bearer hash in one record. There is no Android public key, client certificate, hardware-backed identity assertion, signed request, or Windows host certificate identity in the current bridge.

A device ID can be caller-selected. pair_device removes any record with that same ID before appending the replacement. With unauthenticated pairing, a LAN caller able to name an existing ID can replace its verifier and invalidate the legitimate device’s token. Display name, platform, model, protocol, and build are client-provided metadata, not identity proof.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\models.py lines 54–89; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 251–279, 506–524, 691–727; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 111–120, 261; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\connect\ConnectionPlanner.kt lines 42–52.

## 4. Authentication coverage and endpoint inventory

The common gates below describe requests that reach MobileBridge.handle:

- Mobile Access setting checked first; disabled returns 503 and attempts to stop a stray listener.
- The CV-VL2-A lock resolver runs next in the uncommitted candidate; locked returns 423 before route dispatch, pairing, or authentication.
- Methods are constrained to GET, plus POST for copy/share/save receipts, inbox send, and public pairing.
- All routes other than public pairing require X-Device-Id and Authorization: Bearer …. _authenticate matches the ID, hashes the supplied bearer, rejects revoked records, and returns the paired device.
- Android protocol/app compatibility is checked after authentication for records that declare a platform.
- No route checks per-device scopes or sensitivity/Safe grants.

| Method / route | Data or effect | Authentication and device check | Lock check | Authorization/idempotency |
|---|---|---|---|---|
| GET /mobile/v1/status | Product/API/compatibility status and current paired ID | Required | Candidate-only, central | No scope; repeatable |
| GET /mobile/v1/clips | All clip previews/metadata, including classification and Safe metadata | Required | Candidate-only, central | No sensitive-item/Safe filter; repeatable |
| GET /mobile/v1/clips/{id} | Full clip content and metadata | Required | Candidate-only, central | No per-item scope; repeatable |
| GET /mobile/v1/clips/{id}/asset | Image bytes | Required | Candidate-only, central | No per-item scope; repeatable |
| GET /mobile/v1/search?q=… | Search over all clips; previews/metadata | Required | Candidate-only, central | No per-item scope; repeatable |
| GET /mobile/v1/collections | Collection names | Required | Candidate-only, central | No scope; repeatable |
| GET /mobile/v1/favorites | Favorite clip previews/metadata | Required | Candidate-only, central | No scope; repeatable |
| GET /mobile/v1/recently-removed | Recently removed clip previews/metadata | Required | Candidate-only, central | No scope; repeatable |
| GET /mobile/v1/inbox | Mobile Inbox previews/metadata | Required | Candidate-only, central | No scope; repeatable |
| POST /mobile/v1/clips/{id}/copy | Records a copy receipt; does not copy on the PC or mutate clip content | Required | Candidate-only, central | Same bearer; replay adds receipts |
| POST /mobile/v1/clips/{id}/share | Records a share receipt | Required | Candidate-only, central | Same bearer; replay adds receipts |
| POST /mobile/v1/clips/{id}/save | Records a save receipt | Required | Candidate-only, central | Same bearer; replay adds receipts |
| POST /mobile/v1/inbox/send | Writes text/URL/image into the PC vault; image decoded size capped at 10 MiB | Required | Candidate-only, central | Same bearer as reads; no deduplication key |
| POST /mobile/v1/pair-device | Creates/replaces paired-device record and returns reusable plaintext bearer | **Not required**; device ID/name/platform are caller-supplied | Candidate-only, central | Offer token optional; no per-device scope or rate limit found |

Unknown GET routes are authenticated before returning 404. Forbidden-route patterns return 404 before authentication. Unsupported methods that reach handle return 405; HEAD/OPTIONS fall through to the base HTTP handler. Oversized POST bodies return 413 before handle. None of these exceptional paths dispatches protected content.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\api.py lines 22–89, 101–130, 138–155; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 340–480, 506–524, 574–689, 691–735; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\inbox.py lines 20–25, 45–73, 101–145.

## 5. Authorization model

- **Active/revoked device status:** yes. A paired record is either active (revoked_at is None) or rejected as revoked.
- **Per-device identity field:** yes, but it is not independently authenticated; it is paired with the bearer.
- **Per-device scopes:** no.
- **Per-action permission grants:** no.
- **Read/write separation:** route behavior differs, but authorization does not. The same bearer that reads protected data can use the inbox write route.
- **Send/receive scopes:** no. Send to PC is a route feature, not a grant stored on a device.
- **Sensitive-item or Safe-level permissions:** no. List/search use all clips; detail/asset dispatch does not check classification or Safe membership. The safe_id accepted by mobile send is not a per-device grant.
- **Background reconnect:** Android stores autoConnectApproved and keepConnectedInBackground; defaults are false and the client/service honors them. Windows does not receive or enforce those as authorization scopes. They do not narrow what the bearer can request.

The API’s read-only label is inaccurate as a whole: copy/share/save are receipt-only writes, but /mobile/v1/inbox/send creates vault content.

## 6. Vault Lock interaction

**CV_VL2_A_CANDIDATE_ONLY.** In the dirty candidate diff, MobileBridge.handle adds a lock-resolver check after the enabled check and before method validation, route dispatch, and authentication. Consequently it covers every request routed through handle, including /pair-device, protected routes, unknown routes, and non-GET methods. The source tests assert 423 for a protected clips request and for unauthenticated pairing while locked; those tests were inspected, not run.

No API handler bypasses handle in the reviewed source. The body-size rejection and base-handler HEAD/OPTIONS responses occur outside route dispatch but do not return vault content or perform a Bridge action. Because the lock check precedes authentication, a reachable unauthenticated caller can distinguish locked (423) from unlocked (normally 401); this exposes lock state, not vault content. The check is a request-start check only: a request already past it can continue through authentication/storage and return after a lock transition. Revocation and listener shutdown likewise do not track/cancel in-flight handlers. There is no app-level long-lived authenticated session table; each protected request re-checks the bearer.

After unlock, the next request from an active device is processed normally without re-pairing. Android does not map HTTP 423 to a dedicated vault_locked error type; the client’s generic unknown-status branch receives it. No physical Windows or live Android lock interaction was performed here.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py candidate diff at lines 375–382, request flow lines 340–428; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\tests\test_mobile_bridge.py lines 96–120, 133–169; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 149–158, 206–223.
## 7. Revocation and disable behavior

| Operation | Current effect | Gap |
|---|---|---|
| Windows revoke one | Stamps revoked_at, saves the record; future auth attempts with that ID return 401. Record remains visible as revoked. | Does not cancel an already-authorized handler. No lockout notification/push to Android. |
| Windows revoke all | Marks every active device revoked. | No active-request termination. |
| Re-pair same ID | Replaces the old record with a new token hash; old token fails, new token works, prior revoked state/history for that ID is discarded. | Re-pair can be initiated by unauthenticated public route when offer token is omitted. |
| Disable Mobile Access | Stops mDNS/listener and saves disabled setting. Paired records/tokens remain. | Re-enabling Mobile Access makes retained unrevoked credentials usable again. |
| Android Disconnect | UI stops the background service, then clears encrypted pairing preferences and resets pairing UI state. | It does not call Windows revoke. Windows record and bearer verifier remain active; Android local vault data is separate and is not cleared by PairingStore. |
| Android background reconnect | On start, service is launched when preference permits. It polls every 45 seconds; automatic status verification requires autoConnectApproved. | A revoked/unauthorized result changes the notification to repair guidance but does not itself revoke/clear the PC record or terminate a stolen bearer elsewhere. |
| Token rotation | No standalone rotation endpoint. Generate a new device bearer via pairing/re-pair; same-ID re-pair supersedes the old verifier. | Token has no natural expiry. |

Bridge request receipts are persisted with bounded retention (last 500), and normal revoke calls do not create a Mobile Access request receipt or a separate revoke audit event in the reviewed bridge path. Revoked records remain in settings until same-ID replacement or other settings management.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 281–337, 506–524, 562–572; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\mobile_access_controller.py lines 185–220; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\ui\shell.py lines 5149–5165; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\receipts.py lines 13–40; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\ui\CacheVaultMobileRoot.kt lines 288–310; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\connect\BackgroundConnectionService.kt lines 69–115, 165–169; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\ui\AppViewModel.kt lines 458–461.

## 8. Android client behavior

- QR path extracts host/port/offer token from scanned JSON (or a legacy token-like fallback) and submits over HTTP. The request does not include a certificate fingerprint or TLS pin.
- Discovered-PC path sends a public pair request without an offer token, saves the returned bearer, then verifies status. It reuses a previously stored Android ID on re-pair; otherwise it generates a UUID-derived ID.
- Manual setup stores host, port, device ID, and bearer. PairingSanitize strips whitespace but does not authenticate the selected host. A manually entered endpoint can receive the bearer if the user points setup to the wrong host.
- Protected requests put device ID and bearer in X-Device-Id and Authorization: Bearer … . They use http://, 8-second connect and 12-second read timeouts, and no configured TLS/certificate policy. The default OkHttp retry behavior is not customized here.
- The Android manifest has usesCleartextTraffic=true.
- Pairing is held in EncryptedSharedPreferences; Vault Lock/local-vault storage is separate. Android local Disconnect stops its background service and clears pairing preferences but does not remotely revoke.
- autoConnectApproved and keepConnectedInBackground are client-side preferences. The foreground service polls on a 45-second interval while opted in, auto-verifying only when auto-connect has separately been approved.
- The current deep link opens the paired-PC area; pairing credential material comes from QR/manual setup, not the deep-link URI.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 111–141, 192–223, 254–262; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeRepository.kt lines 72–140; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\PairingStore.kt lines 7–64, 85–99; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\Models.kt lines 3–58; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\ui\AppViewModel.kt lines 354–460; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\connect\BackgroundConnectionService.kt lines 69–115; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\AndroidManifest.xml lines 14–39.

## 9. Secret and metadata exposure

Reviewed Bridge paths show:

- **HTTP request/access logging:** one handler override suppresses the default request log callback. No request-body logger was found in that handler.
- **Receipt schema:** zero credential/token/body fields. It records timestamp, action, route, result, device ID/name, clip ID, reason, remote IP, and suggested fix. Pairing receipts include device metadata and remote IP, not the returned bearer.
- **Credential storage:** Windows settings store only the bearer hash; Android encrypted preferences store the reusable bearer. Pairing offer is process-memory state and is serialized into QR JSON. The successful pairing response includes the plaintext bearer.
- **UI/clipboard:** Windows displays the permanent token behind a Show Token control and provides Copy Token/Copy All Setup Info. QR payload contains the offer token and has a Copy QR Payload action. These are intentional user-visible/copy surfaces, not server log output.
- **Android diagnostics/errors:** reviewed BridgeClient has no logging interceptor; generic unexpected HTTP errors retain response-body text in BridgeError.Unknown. No token value is added by the server’s ordinary error bodies in the reviewed code. This is not a claim about OS-wide network diagnostics or third-party tooling.
- **Content:** list/search return previews; detail returns full clip content and image asset returns bytes. Receipts do not store content bodies. Mobile inbox writes content into the vault and capture/event history as intended.
- **Transport exposure:** because requests and responses are plain HTTP, bearer headers, pairing response token, offer body, clip content, image bytes, and mobile-send bodies can be observed or modified by an on-path LAN actor. Suppressed app logs do not protect traffic in transit.

No live settings, logs, tokens, pairing QR, local database, or device storage were opened for this audit.

**Evidence:** C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\bridge.py lines 165–206, 409–420; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\models.py lines 92–116; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\core\mobile\receipts.py lines 13–40; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeClient.kt lines 138–141, 192–223; C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\cache_vault\ui\mobile_dialogs.py lines 198–248, 278–280, 411–422.
## 10. Threat-boundary matrix

| Threat | Current resistance / result | Classification |
|---|---|---|
| Stolen bearer credential | Random high-entropy bearer; Android encrypts its stored copy; Windows stores a SHA-256 verifier. No expiry, TLS protection, or scope reduction; attacker can use it until revoked/replaced while listener and policy allow. | PROVEN_CURRENT |
| Copied pairing QR/code | QR offer expires after five minutes and sequential use is rejected if offer token is supplied. The token is visible in QR/copy and is sent over HTTP. Offer is optional, not bound to a client key, and concurrent atomic consumption is unproven. Manual device token has no expiry. | PROVEN_CURRENT / UNKNOWN for concurrent race |
| Replayed pairing request | No-offer request can be replayed; same-ID replay replaces current verifier. Supplied offer blocks sequential replay only. | PROVEN_CURRENT |
| Replayed authenticated request | Bearer is reusable; no nonce/idempotency key. Repeated inbox send can create repeated vault items; receipt posts can repeat. | PROVEN_CURRENT |
| Unauthorized LAN peer | Can reach default all-interface listener and self-pair through no-token route while Mobile Access is enabled and lock is open. | PROVEN_CURRENT |
| Revoked device | Future requests are rejected by revoked_at; in-flight authorized operation is not cancelled. | PROVEN_CURRENT |
| Lost phone | Windows user can revoke it. Android Disconnect alone only removes local pairing; no server push revocation exists. | PROVEN_CURRENT |
| Stale Android installation | A still-active bearer remains accepted regardless of whether the intended installation is still used; owner must revoke. Compatibility check is not cryptographic identity. | PROVEN_CURRENT |
| Lock-state bypass | Candidate checks all bridge-dispatched requests centrally, including public pairing. An already-admitted request can finish after lock. The pre-auth check also exposes a locked/unlocked status oracle to reachable callers. Live hardware/runtime behavior remains unverified. | CV_VL2_A_CANDIDATE_ONLY |
| Mobile Access disabled bypass | Controller stops listener/advertisement; handler also returns 503 if reached after disabled state. Credentials are retained and become usable again if re-enabled. | PROVEN_CURRENT |
| Credential in app logs/events | Request logging is suppressed; receipts omit credential and body. UI/QR/clipboard and HTTP response are deliberate exposure points. OS/network logs are unverified. | PROVEN_CURRENT / UNKNOWN for OS tooling |
| Traffic observation on LAN | No transport encryption; sensitive headers and payloads are plaintext on the wire. No live packet capture was run. | PROVEN_CURRENT from source; runtime capture UNKNOWN |
| Active LAN modification / MITM | No TLS/server authentication/client pinning; cleartext traffic can be altered by an on-path actor. No live attack test was run. | PROVEN_CURRENT from source; runtime exploit UNKNOWN |

## 11. Migration fit

| Proposed boundary | Current fit | Disposition |
|---|---|---|
| TrustedDevice.device_id, display name, platform, version/model/build | Corresponding PairedDevice fields already exist. | REUSE fields; EXTEND their validation and state semantics. |
| Created/last-seen/revoked | Existing timestamps are present; revocation is a timestamp and online status is derived. | REUSE storage; EXTEND to explicit trust state and audit-preserving transitions. |
| Device identity/public-key binding | No key/certificate identity exists. | PLANNED; do not label device ID or bearer as identity. Defer public-key identity until key lifecycle/migration is justified. |
| Granted scopes/background permission | No server scopes; background preferences live only on Android. | EXTEND schema and server enforcement later, with explicit migration/consent policy. |
| Pairing offers | Already a separate in-memory PairingOfferManager. | REUSE concept; EXTEND to mandatory, atomic consume and authenticated transport binding. |
| Transport/session credentials | Current bearer is stored alongside device record; Android combines host, ID, bearer, and reconnect preferences in PairingConfig. | EXTEND/MIGRATE by separating endpoint pin and bearer from trust metadata; replace cleartext HTTP transport. |
| Active sessions | No application-level session registry; each request reauthenticates. | Keep per-request authentication for the first tranche; do not add session machinery without a requirement. |
| Receipts/events | Bridge receipts exist but are metadata-only and do not record revoke transitions. | REUSE request receipts; EXTEND with safe lifecycle audit events that never include secrets/content. |

## 12. Candidate first hardening tranche

### CV-DT1B-1 — CLOSE ENROLLMENT AND PROTECT THE EXISTING BEARER TRANSPORT

This is a proposed implementation tranche, not current behavior (**PLANNED**). Do not add device scopes, high-risk remote actions, Windows Hello, or public-key device identity in this tranche.

**Trust boundary:** Windows listener ↔ Android client; from pairing offer issuance through every bearer-authenticated request and revocation.

**Windows files / changes:**

- cache_vault/core/mobile/bridge.py: wrap the listener in TLS; reject /pair-device unless a valid offer is supplied; ensure same-ID replacement can only follow that explicit enrollment flow; keep lock and Mobile Access checks before any route operation.
- cache_vault/core/mobile/pairing_offer.py: make offer consumption atomic under concurrent requests; include the server certificate/public-key fingerprint in the QR pairing payload; ensure offers are one-grant and expire on process restart.
- Add a narrowly scoped Windows TLS identity module (new file) to create and retain a stable server certificate/key with owner-only storage and rotation rules. Do not store the private key in settings JSON or logs.
- cache_vault/ui/mobile_dialogs.py and cache_vault/ui/shell.py: make secure QR/manual setup explicit. Manual setup must carry a verifiable server fingerprint; do not retain a no-pin HTTP fallback.

**Android files / changes:**

- android/app/src/main/java/com/prooffoundry/cachevaultmobile/data/BridgeClient.kt: require HTTPS and enforce the enrolled server pin for pairing and every later request.
- C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\BridgeRepository.kt, C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\Models.kt, and C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\data\PairingStore.kt: persist the server pin separately from device_id and bearer; require the one-time offer in every network pairing flow; do not auto-pair a discovered service without an offer.
- C:\Users\KickA\Projects\Active\CV-VAULT-LOCK-2\android\app\src\main\java\com\prooffoundry\cachevaultmobile\ui\AppViewModel.kt and QR/manual setup screens: parse/validate the fingerprint and remove the no-offer enrollment route from user flows.
- android/app/src/main/AndroidManifest.xml: disallow cleartext traffic.

**Migration:** No Windows paired-device data migration is needed to add transport support, but existing Android pairings have no authenticated-server pin. Require one explicit re-pair through the new QR/manual flow before trusting TLS; preserve/revoke the old Windows record through same-ID replacement or Windows revoke. Add a pin field to Android local pairing preferences with old entries treated as unpinned and unusable until re-paired. Keep bearer verifier format unchanged for the first tranche.

**Compatibility:** Release Windows and Android changes together or gate the TLS protocol explicitly. Old clients use HTTP and will not interoperate with the TLS-only listener; do not silently downgrade. Existing pairings require re-enrollment to acquire a pin.

**Tests and qualification:**

- Windows tests: no-token/empty-token pairing is rejected; valid, expired, malformed, replayed and concurrent offer consumption; same-ID replacement only with valid offer; TLS-only listener; every protected route and pairing path returns lock/disabled gates correctly; revoke future requests; no secret in receipts/log hooks.
- Android tests: reject untrusted/changed certificate; pin verified during initial pairing and subsequent calls; no cleartext request; discovery cannot pair without a QR offer; migration marks old pairing as requiring re-pair; disconnect continues to clear only local credentials.
- Cross-version tests: new desktop/new Android works; old Android fails closed with actionable upgrade/re-pair guidance; no HTTP fallback.
- Runtime qualification: capture traffic and verify credentials/content are not plaintext; test Windows lock/disable and live paired Android behavior; bind evidence to exact candidate/package identities.

**Rollback:** Treat server TLS identity and Android pin as paired state. Do not fall back to HTTP when pin/TLS validation fails. If rollback is required, disable Mobile Access until a coordinated version with a trusted pin is restored; otherwise bearer credentials return to cleartext exposure. Existing bearer hashes can remain or be revoked; do not silently erase device/event history.

This transport tranche does not encrypt the Windows database or image files at rest. It deliberately keeps the current bearer credential and paired-device record shape, while closing public enrollment and preventing LAN observers/MITM from reading or modifying bridge traffic. Device key identity, scopes, and a richer Trusted Devices UI can follow only after this boundary is qualified.

## 13. Qualification and custody

- No tests were run; existing test source was reviewed only.
- No live Windows runtime, Android device, packet capture, settings file, log, token, QR image, or database was inspected.
- The report is the only file created by this audit. Product source and tests were not written, formatted, or tested.
- The frozen candidate identity recorded before this audit was ffa3db0e015e4129d3a6dda4dbb29ad979d19697faac0bd6dd0d925854b300d2 for 13 files.
- Recalculation using the explicit 13-file manifest below and this deterministic byte-level SHA-256 encoding produced bdc2e0e438ac17bc04888f5d295fe80b6d4ac07f8fb01179614cf3619603aa55. The audit wrote none of those 13 files. The previous record did not preserve its manifest/serialization in the repository, so the two values do not currently reconcile. Keep the originally frozen digest as the physical gate’s expected value; reconcile the hash procedure before treating the new digest as the same identity.

Hash encoding used for the recomputation:

    SHA256(
      UTF8("BASE=3af328424c39d97d4af54156672a2e4b2d2b8c43\n") ||
      for each of these 13 paths in ordinal ascending order:
        UTF8(path with '/' separators) || 0x00 || UINT64_LE(file byte length) || file bytes
    )

Manifest:

    cache_vault/core/mobile/bridge.py
    cache_vault/core/settings.py
    cache_vault/core/vault_lock.py
    cache_vault/modules/registry.py
    cache_vault/ui/dialogs.py
    cache_vault/ui/shell.py
    cache_vault/ui/vault_lock.py
    cache_vault/ui/windows_session_lock.py
    review/CV-VAULT-LOCK-2-20260924/RECONCILIATION.md
    tests/test_command_center_app.py
    tests/test_mobile_bridge.py
    tests/test_vault_lock.py
    tests/test_vault_lock_ui.py

CURRENT_TRANSPORT = PROVEN_CURRENT: plain HTTP, all IPv4 interfaces by default, mDNS while enabled; no TLS/pinning.

CURRENT_DEVICE_IDENTITY = PROVEN_CURRENT: PARTIAL; caller-supplied ID plus metadata and bearer, no independent cryptographic device identity.

CURRENT_AUTHENTICATION = PROVEN_CURRENT: reusable bearer + device ID for protected routes; unauthenticated pairing route accepts absent offer token.

CURRENT_AUTHORIZATION = PROVEN_CURRENT: all-or-nothing active paired-device access; no scopes or sensitivity/Safe grants; authenticated inbox write is available.

CURRENT_REVOCATION = PROVEN_CURRENT: future requests rejected after Windows revocation; no active-handler cancellation; Android disconnect is local-only; disable retains credentials.

LOCK_INTEGRATION = CV_VL2_A_CANDIDATE_ONLY: central 423 gate covers bridge-dispatched requests, including pairing; in-flight request may finish; no runtime qualification here.

SECRET_EXPOSURE = PROVEN_CURRENT: token hash in Windows settings JSON, bearer in Android encrypted preferences; QR/manual UI and HTTP response expose plaintext by design; no Bridge receipt/access-log credential field; transport sends bearer/payloads in clear.

FIRST_HARDENING_TRANCHE = PLANNED: mandatory atomic pairing offer plus TLS with QR/manual certificate pinning; retain bearer/device schema initially; no silent HTTP fallback.

CV_DT1A = COMPLETE
SOURCE_CHANGED = NO
CV_VL2_A_CANDIDATE_HASH = bdc2e0e438ac17bc04888f5d295fe80b6d4ac07f8fb01179614cf3619603aa55
PREVIOUSLY_RECORDED_FROZEN_HASH = ffa3db0e015e4129d3a6dda4dbb29ad979d19697faac0bd6dd0d925854b300d2
HASH_IDENTITY_RECONCILIATION = PENDING
