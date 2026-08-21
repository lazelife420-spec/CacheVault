# Cache Vault — E4 Design Proposal: LAN-IP / Interface Selection

**Date:** 2026-08-20
**Status:** DESIGN ONLY — no source code modified. Canonical `master` remains at `2e90b46b09dba6032e54ce9fdebb6299020723c8`, unchanged.
**Scope:** read-only analysis of the LAN-IP/network-interface-selection path across the desktop app and the Android companion, followed by a concrete design proposal, acceptance criteria, and test cases. This is a design/proof gate, not a code transplant — nothing here is committed or authorized for implementation yet.

---

## 1. Current behavior — the actual mechanism, traced precisely

`cache_vault/core/lan_ip.py` is the single source of truth. Four functions matter:

- **`list_lan_ipv4()`** — gathers candidate addresses two ways: (a) opens a UDP socket, "connects" it to `8.8.8.8:80` (no packet is actually sent; this is the standard portable trick for asking the OS routing table "which local IP would you use to reach this destination"), and takes `getsockname()[0]` — call this the **outbound-preferred address**; (b) enumerates every IPv4 address `socket.getaddrinfo(hostname, ...)` returns for the local machine, excluding loopback. Returns the **union**, sorted by `_private_sort_key`: tier 0 = `192.168.x`, tier 1 = `10.x`, tier 2 = `172.16–31.x`, tier 3 = everything else; **within a tier, plain lexicographic string comparison** (not numeric — `"192.168.10.1"` sorts before `"192.168.2.1"` because `'1' < '2'` as characters).
- **`recommended_lan_ipv4(ips=None)`** — returns the first address matching `192.168.` or `10.` prefix from the (already-sorted) list, else the first address in the list regardless of range, else `None`.
- **`advanced_lan_ipv4(ips=None)`** — everything else, for display.
- **`lan_ip_guidance(ips, port)`** — human-readable pairing instructions built from the above.

**The core weakness:** the outbound-preferred address (a) is computed but then **discarded into an unordered set** alongside every other detected address (b) — it gets no special treatment once merged. The final choice is decided entirely by the tier/lexicographic sort, not by which address the OS itself would actually route outbound traffic through. Two same-tier addresses (e.g., a real Wi-Fi adapter at `192.168.1.50` and a VMware/VirtualBox host-only adapter at `192.168.150.1`, both common on developer machines) are ordered by string comparison of the address text, which has no relationship to which one is real, active, or reachable from another device on the network.

## 2. Complete consumer inventory, classified by actual impact

Every call site in the desktop codebase was traced individually — not assumed from the function names alone.

### Functionally consequential (affects what the phone is actually told to connect to)

| Call site | What it does | Existing safeguard |
|---|---|---|
| `cache_vault/core/mobile/bridge.py::MobileBridge.create_pairing_offer` (`host=None` → `recommended_lan_ipv4(list_lan_ipv4())`) | Embeds the picked address as the `host` field in the **QR-code pairing payload** — the address a phone scanning the code will try to connect to. This is the path actually wired in the shipped app: `shell.py:4895` passes `create_pairing_offer=self._mobile_bridge.create_pairing_offer` into `PairAndroidDialog`, and `_generate_qr_offer()` calls it with **zero arguments**, so `host=None` and the internal, unguarded `recommended_lan_ipv4()` call is what actually executes. | **None.** No tier sanity-check before trusting the pick. |
| `cache_vault/core/mobile/discovery.py::_lan_addresses` (mDNS/`zeroconf` advertisement) | Chooses which address(es) the desktop advertises via mDNS for the Android `NsdManager` to auto-discover. | **Yes** — its own docstring explicitly documents the exact risk (a Hyper-V/WSL virtual adapter causing "No Cache Vault PC found"), and only trusts `recommended_lan_ipv4()`'s pick if it's *already* in the `192.168.`/`10.` tier; otherwise falls back to advertising every detected address. Covered by 3 dedicated tests in `tests/test_mobile_discovery.py`. |

**Important asymmetry:** the QR-code path (the one actually wired into the shipped Pair Android dialog) has *no* defensive check; the mDNS path does. A wrong pick is not equally risky across the two mechanisms today.

### Display/informational only (no functional network consequence)

- `cache_vault/core/mobile/connection_doctor.py::connection_doctor_report` — diagnostics panel text.
- `cache_vault/ui/mobile_dialogs.py::PairAndroidDialog` — "Recommended connection" label text, Advanced-section list, and a **locally redundant** `recommended_lan_ipv4()` call inside `_generate_qr_offer` (line 236) that is dead in the real wired path, since the live `create_pairing_offer` callback (from `bridge.py`) ignores it and recomputes its own.
- `cache_vault/ui/settings_hub.py::_verify_and_complete` — a "Saved — Listening on {ip}:{port}" confirmation *message*. The actual bind address is `settings.mobile_access_bind_host or DEFAULT_BIND_HOST` (`"0.0.0.0"` by default, all interfaces) — entirely independent of `recommended_lan_ipv4()`.
- `cache_vault/ui/pairing_help.py::pairing_host_for_copy` / `pairing_vault_display_text` — "copy pairing info" manual-entry text.
- `cache_vault/modules/mobile_bridge/__init__.py` — Settings Hub status row, via a background-resolved, deadline-bounded `LanIpResolver` (never blocks the UI thread).

**Load-bearing correction to the original salvage-audit framing:** the risk of a wrong `recommended_lan_ipv4()` pick is **not** "data goes to the wrong place" or a security concern — the bridge server itself binds to `0.0.0.0` (or whatever the user explicitly configured) regardless of this function's output. The actual, sole consequence of a wrong pick is **pairing convenience**: the QR code / mDNS advertisement points the phone at an address it cannot reach, and pairing fails with a generic "can't find PC" / connection-refused symptom rather than any data or security exposure. This changes the design's risk *severity* (real, worth fixing, UX-impacting) without changing its risk *class* (not a security or correctness-of-data issue).

## 3. Android companion behavior — confirms zero fallback exists downstream

`android/app/src/main/java/com/prooffoundry/cachevaultmobile/connect/PcDiscovery.kt`: `NsdManager.ResolveListener.onServiceResolved` takes `s.host?.hostAddress` — a single resolved address — and returns immediately via `finish(...)`. There is no retry across multiple candidate addresses, no "try the next one if this fails" logic anywhere in this file. This matches `discovery.py`'s own docstring claim ("Android's `NsdManager` resolves a single host") and confirms it's accurate, not just asserted.

`PairingSelfHealTest.kt`'s "self-heal" machinery (`PairingSanitize.isUsableHost`) validates that a *stored* host string looks like a plausible address (rejects things like the literal string `"Cache Vault Desktop"` being mistakenly persisted as a host) — this is data-hygiene, not multi-adapter resilience. It does nothing to recover from a syntactically-valid but unreachable IP (e.g., a Hyper-V address).

**Conclusion: the desktop side is the only layer that can prevent this failure mode. The phone will not recover from a bad pick on its own.**

## 4. Failure modes — grounded in the traced mechanism, not hypothetical

| Scenario | Current behavior | Outcome |
|---|---|---|
| Single real adapter (typical home user, no VMs/VPN) | Only one candidate in the `192.168.`/`10.` tier; sort is moot | **Correct today.** No regression risk from doing nothing. |
| Real Wi-Fi + a virtualization host-only adapter (VMware/VirtualBox/Hyper-V), both same tier | Lexicographic string sort decides — genuinely arbitrary, can go either way depending on the exact octets involved | **Silent coin-flip.** Sometimes picks the virtual adapter; QR/mDNS path both affected (mDNS has its own tier-gate but that doesn't discriminate *within* a tier). |
| Real Wi-Fi + Hyper-V/WSL virtual adapter (commonly `172.x`, a lower-priority tier) | Real adapter wins by tier | **Correct today** — this is the specific case `_lan_addresses()`'s docstring already documents fixing. |
| Split-tunnel VPN (most common Windows VPN client mode — only specific routes go through the tunnel) | The outbound-preferred trick (`8.8.8.8` UDP connect) typically still resolves to the real physical interface, since general internet-bound traffic isn't tunneled | **Likely unaffected either way**, since the outbound-preferred signal isn't even being trusted specially today. |
| Full-tunnel VPN (all traffic routed through the tunnel, including the `8.8.8.8` probe) | The outbound-preferred address becomes the VPN's virtual tunnel IP. Under the *current* algorithm this address is just one more entry in the set — it wins only if it also happens to sort first within its tier, so today it's a coin-flip, not a guaranteed wrong answer. | **Coin-flip today; would become a guaranteed wrong answer under a design that blindly trusts the outbound-preferred address without any exclusion.** This is exactly the risk the prior salvage audit (item B2, score 61/100) flagged in the quarantined historical candidate — that candidate force-sorted the outbound-preferred address first with no VPN/virtual-adapter exclusion at all. |
| No usable address at all (offline, airplane mode, etc.) | `recommended_lan_ipv4` returns `None`, `lan_ip_guidance` shows a clear "Could not detect... run ipconfig" fallback message | **Correct today**, already has an explicit, tested fallback path. |

**The central design tension, precisely restated:** anchoring the selection to the OS's own outbound-routing decision fixes the "arbitrary same-tier coin-flip" cases, but naively trusting it unconditionally introduces a *new*, previously-absent guaranteed-wrong case under full-tunnel VPN. Today's algorithm is arbitrary-but-bounded (never worse than "some detected LAN-tier address," never actively prefers a VPN tunnel); a naive fix could be actively worse in one specific, real scenario. Any accepted design must not regress the full-tunnel-VPN case while fixing the same-tier-coin-flip case.

## 5. Current test coverage — where the real gaps are

| Area | Coverage |
|---|---|
| `LanIpResolver` caching/threading/deadline behavior | 6 tests, `tests/test_lan_ip_resolver.py` — solid |
| `_lan_addresses()` mDNS tier-gate (reachable-only / fallback-to-all / empty) | 3 tests, `tests/test_mobile_discovery.py` — solid |
| `list_lan_ipv4()`'s own ordering/tie-break logic, in isolation | **None.** |
| `recommended_lan_ipv4()`'s multi-adapter tie-break behavior | **None.** |
| `bridge.py::create_pairing_offer`'s host selection (the QR-code path — the one with no tier-gate) | **None.** `tests/unit/test_pairing_offer.py` covers token/expiry mechanics only. |
| Any VPN / full-tunnel scenario, in either direction | **None**, anywhere in the suite. |

Both the *current* behavior and *any* proposed fix are, today, equally unvalidated for the multi-adapter and VPN cases specifically — this is a real gap independent of which design direction is chosen.

## 6. Design proposal

### Options considered

**Option A — do nothing.** Rejected: the same-tier coin-flip is real and undefended, and the asymmetry between the QR path (undefended) and mDNS path (defended) is itself worth closing even if the underlying algorithm doesn't change.

**Option B — port the historical quarantined candidate as-is** (force outbound-preferred address to sort first, unconditionally). Rejected, per the original salvage audit's own finding: fixes the coin-flip but introduces a guaranteed-wrong pick under full-tunnel VPN, with no exclusion logic at all.

**Option C (recommended) — trust the outbound-preferred signal only when it doesn't look like it crossed a VPN/tunnel boundary, using signals already available without a new dependency.** Concretely:

1. Keep gathering candidates exactly as today (outbound-probe address ∪ `getaddrinfo` enumeration) — no change to *what* is detected, only to *ordering/selection*.
2. When the outbound-preferred address is present in the candidate set, prefer it **only if it is also in the existing `192.168.`/`10.`/`172.16-31.` tier scheme** — i.e., apply the *same* tier-sanity-check `_lan_addresses()` already uses for mDNS, uniformly, to the general recommendation logic too. This closes the asymmetry (§2) without inventing a new heuristic: it reuses a pattern already shipped, tested, and battle-tested in this exact codebase.
3. This alone does **not** fully solve full-tunnel VPN: a VPN's virtual adapter can itself present a `10.x` address (common in corporate VPN configs) and would still pass the tier check. A conservative second signal is needed. Two candidates, in order of preference:
   - **3a (no new dependency):** Windows-only, using the `pywin32` dependency this project already requires (`requirements.txt: pywin32>=306; platform_system == "Windows"`) to call `GetBestInterfaceEx`/`GetAdaptersAddresses` (via `ctypes` + `iphlpapi.dll`, the same low-level approach the project already uses elsewhere for Windows-specific integration) and cross-reference the outbound-preferred address against the adapter's reported interface *type* (Ethernet/Wi-Fi vs. PPP/tunnel/loopback-class adapters, which Windows itself distinguishes). This is more precise than IP-range heuristics and directly answers "is this a virtual/tunnel adapter" instead of guessing from the address text.
   - **3b (fallback, always available):** if 3a's Windows API path is judged too large a change for this gate, keep the current text-heuristic tier check as the *only* signal (accept that full-tunnel VPN remains a coin-flip, exactly as it is today) and treat this as an explicitly deferred, separately-scoped follow-up — not silently declared solved.
4. Whichever selection wins, **fix the same-tier lexicographic-string tie-break bug** (§1) as a small, independent, low-risk correctness fix regardless of which of the above is chosen — sorting `"192.168.10.1"` ahead of `"192.168.2.1"` by string comparison is a plain bug, unrelated to the VPN question, and should not block or be entangled with it.
5. Consolidate the QR-code path's redundant, dead `recommended_lan_ipv4()` call in `mobile_dialogs.py:236` — either remove it (since the live wired path never uses it) or make `_create_pairing_offer`'s contract explicit about which address wins, so there is exactly one place computing this, not two that can silently drift apart.

**Recommendation: adopt 3b as the E4a (small, bounded) gate — tier-check reuse + tie-break bug fix + dead-code consolidation, all independently low-risk and immediately testable — and scope 3a (the Windows-API-backed VPN/virtual-adapter discriminator) as a separate, explicitly-authorized E4b gate**, since it is meaningfully larger in surface area (new Windows API surface, needs its own dedicated test harness against real adapter enumeration) and deserves its own review rather than being bundled into "the LAN-IP fix."

## 7. Acceptance criteria

**For E4a (tier-check reuse + tie-break fix + dead-code consolidation):**
- A. `recommended_lan_ipv4()` never returns an address outside the `192.168.`/`10.`/`172.16-31.` tier when at least one in-tier address exists in the candidate set (matching `_lan_addresses()`'s existing contract, applied uniformly).
- B. Within a single tier, ordering is by actual numeric octet comparison, not lexicographic string comparison — `"192.168.2.1"` must sort before `"192.168.10.1"`.
- C. When the outbound-preferred address (the `8.8.8.8`-probe result) is present and in-tier, it is preferred over other same-tier candidates that are not the outbound-preferred address.
- D. The QR-code pairing-offer path (`bridge.py::create_pairing_offer`) and the mDNS advertisement path (`discovery.py::_lan_addresses`) select consistently from the same underlying recommendation for the same candidate set — no more silent asymmetry between the two.
- E. `mobile_dialogs.py`'s locally-recomputed, dead `recommended_lan_ipv4()` call is either removed or demonstrably reconciled with the live wired path — no two independent computations that can disagree.
- F. No regression to the already-correct, already-tested cases: single-adapter, Hyper-V/WSL-lower-tier, and no-usable-address-at-all.
- G. Full-tunnel VPN remains **no worse than today** (still a coin-flip, not a new guaranteed-wrong answer) — explicitly verified, not assumed, and explicitly documented as an accepted, deferred limitation pending E4b.

**For a future E4b (Windows-API-backed VPN/virtual-adapter discrimination), if separately authorized:**
- H. Given a real interface-type signal, the recommendation excludes addresses on adapters Windows itself classifies as tunnel/PPP/virtual, even when those addresses fall in an otherwise-preferred tier.
- I. Graceful degradation: if the Windows API call fails or is unavailable (non-Windows, restricted environment, API error), fall back to the E4a behavior exactly — never a hard failure of pairing/discovery because of this enhancement.

## 8. Test cases (for E4a; to be written before any production change, per this project's established regression-first practice)

Using `monkeypatch` to control `socket.socket().getsockname()` and `socket.getaddrinfo()`, matching the existing style in `tests/test_lan_ip_resolver.py` / `tests/test_mobile_discovery.py`:

1. Single `192.168.x` address → returned as-is (no regression).
2. Real `192.168.x` Wi-Fi + Hyper-V `172.x` → Wi-Fi wins (existing, must still pass).
3. Two same-tier `192.168.x` addresses, outbound-preferred is the *lexicographically later* one → outbound-preferred wins (this is the specific coin-flip case currently broken; the fix must invert what today's code does here).
4. Numeric tie-break: candidates `"192.168.2.1"` and `"192.168.10.1"` in the same tier, neither is the outbound-preferred address → `"192.168.2.1"` sorts first (proves the lexicographic bug is fixed, independent of the outbound-preference feature).
5. Outbound-preferred address is *not* in any preferred tier (simulating a full-tunnel VPN scenario where the probe resolves to, say, a `100.64.x.x` CGNAT-style tunnel address) → recommendation falls back to the best in-tier address from the `getaddrinfo` enumeration, **not** the out-of-tier outbound-preferred address (proves G — no new guaranteed-wrong case).
6. Outbound-preferred address is in-tier but is itself a plausible VPN address (e.g., `10.x` from a corporate VPN client) with a genuine physical `192.168.x` adapter also present → documents the accepted E4a limitation (coin-flip, not fixed) with an explicit test marked/labeled as a known-limitation case, not silently passing by accident.
7. No addresses detected at all → `None`, unchanged fallback text path.
8. `bridge.py::create_pairing_offer(host=None)` and `discovery.py::_lan_addresses()` given the identical candidate set → assert they agree on the same address (proves D).
9. `mobile_dialogs.py::_generate_qr_offer` with the real wired `create_pairing_offer` callback → assert only one recommendation computation occurs / the dead call is gone (proves E), via a call-count or removed-code assertion depending on the chosen implementation.

## 9. Explicitly out of scope for this design

- Any change to `lan_ip.py`'s public function signatures beyond what's needed for the above (no API redesign).
- The `172.16-31.` tier's own internal ordering — not touched, no evidence of a problem there.
- Non-Windows platforms — this project is Windows-only in practice (`pywin32` is an unconditional runtime dependency for the packaged app); a cross-platform interface-type API is not proposed.
- iOS — no iOS client exists (confirmed in the canonical record's own README audit from Gate 4 of the earlier canonicalization pass).
- Reworking `DEFAULT_BIND_HOST`/the actual server bind behavior — confirmed unrelated to this function's output (§2), not touched.

## 10. Bounded next gate, if authorized

**E4a** as scoped in §6/§7/§8 above: tier-check reuse, numeric tie-break fix, and QR/mDNS-path consolidation, each independently testable, each independently low-risk, none touching Windows-API surface. This would follow the same regression-first, minimal-diff, fast-forward-canonicalization pattern as E1–E3. **E4b** (Windows API-backed VPN/virtual-adapter discrimination) is a larger, separate design surface and should get its own authorization and its own review after E4a lands and is proven, not bundled in.

This document proposes; it does not implement. No code has been modified. Canonical `master` remains `2e90b46b09dba6032e54ce9fdebb6299020723c8`.
