# Cache Vault — Salvage E4a Canonicalization Receipt

**Date:** 2026-08-20
**Gate:** Cache Vault Salvage E4a canonicalization — LAN-IP Selection Correctness

## Topology

| | |
|---|---|
| Pre-E4a canonical `master` SHA | `2e90b46b09dba6032e54ce9fdebb6299020723c8` (post Salvage E3) |
| E4a candidate SHA | `45aac5f7c7a3d31187d27bbefc8f7efc491ae497` on `fix/lan-ip-selection-e4a` |
| Rollback tag | `pre-salvage-e4a-lan-ip` → `2e90b46b09dba6032e54ce9fdebb6299020723c8` (verified via `git rev-parse`, intact) |

Preconditions confirmed before the move: `master` was exactly `2e90b46b09dba6032e54ce9fdebb6299020723c8`; candidate branch `fix/lan-ip-selection-e4a` was exactly `45aac5f7c7a3d31187d27bbefc8f7efc491ae497`; rollback tag pointed exactly to `2e90b46b09dba6032e54ce9fdebb6299020723c8`; working tree was clean (tracked files).

## Fast-forward

```
git merge --ff-only 45aac5f7c7a3d31187d27bbefc8f7efc491ae497
Updating 2e90b46..45aac5f
Fast-forward
 cache_vault/core/lan_ip.py     |  53 +++++++++---
 tests/test_lan_ip_selection.py | 177 +++++++++++++++++++++++++++++++++++++++++
 2 files changed, 219 insertions(+), 11 deletions(-)
```
No merge commit created.

## Tree identity proof

```
git rev-parse master                                                    → 45aac5f7c7a3d31187d27bbefc8f7efc491ae497
git rev-parse 45aac5f7c7a3d31187d27bbefc8f7efc491ae497                  → 45aac5f7c7a3d31187d27bbefc8f7efc491ae497
git diff master 45aac5f7c7a3d31187d27bbefc8f7efc491ae497 --exit-code    → zero diff (exit 0)
git status --short                                                      → clean (only unrelated pre-existing untracked process files)
```

## Test results (run fresh against the now-canonical checkout)

| Gate | Result |
|---|---|
| 9 focused E4a tests (`tests/test_lan_ip_selection.py`) | **9 passed**, 0.13s |
| Network/discovery/mobile-pairing regression set — `test_lan_ip_resolver.py`, `test_mobile_discovery.py`, `test_mobile_pairing.py`, `test_connection_doctor.py`, `test_settings_hub.py`, `test_pairing_offer.py` | **67 passed, 0 failed**, 23.19s |
| `python app.py --selftest` | **PASS**, exit 0 |
| Syntax/import validation (`ast.parse` + live import) on `cache_vault/core/lan_ip.py` and the full consumer chain (`bridge`, `discovery`, `connection_doctor`, `mobile_dialogs`, `pairing_help`, `settings_hub`) | **PASS** |
| `git diff --check` (rollback tag → canonical `master`) | **clean** |

Combined with the focused suite, this reproduces the exact 76-passed, 0-failed total from E4a's own implementation validation, now re-confirmed against the canonical tree post-fast-forward.

## Changed files

```
git diff --name-status 2e90b46b09dba6032e54ce9fdebb6299020723c8 45aac5f7c7a3d31187d27bbefc8f7efc491ae497
M	cache_vault/core/lan_ip.py
A	tests/test_lan_ip_selection.py
```
Exactly two files. `bridge.py`, `discovery.py`, `mobile_dialogs.py` untouched — the fix at the shared root (`list_lan_ipv4`/`_private_sort_key`) was sufficient for both the QR-code and mDNS consumers to inherit the corrected behavior automatically.

## What changed, precisely

1. **Numeric tie-break**, replacing lexicographic string comparison within a tier — `"192.168.10.1"` no longer incorrectly sorts ahead of `"192.168.2.1"`.
2. **Outbound-route preference as a same-tier tie-break only** — the OS's own outbound-routing choice (the `8.8.8.8` UDP-probe address) now wins a same-tier coin-flip (e.g., real Wi-Fi vs. a VMware/VirtualBox host-only adapter), but never overrides tier ranking. An out-of-tier outbound-preferred address (the full-tunnel-VPN case) cannot become a new guaranteed-wrong pick — the best in-tier candidate still wins on tier alone.

## Accepted E4a limitation (documented, not concealed)

A VPN address that lands in the **same** tier as a genuine physical adapter (e.g., a corporate VPN issuing `10.x` while the real LAN is also `10.x`) is not distinguishable by IP-range heuristics alone. This is explicitly pinned by `test_outbound_preference_does_not_resolve_same_tier_vpn_ambiguity` in `tests/test_lan_ip_selection.py`, asserting the specific (accepted, not "correct") outcome rather than leaving the case unverified. Resolving this requires real interface-type discrimination — deferred to E4b.

## Confirmation of scope discipline

- **No Android changes** — `android/` untouched, confirmed by the changed-files list above.
- **No bridge-binding changes** — `settings.mobile_access_bind_host`/`DEFAULT_BIND_HOST` (`"0.0.0.0"`) logic in `bridge.py` is untouched; `recommended_lan_ipv4()`'s output was never the bind address, only the advertised pairing endpoint (established in the E4 design investigation, §2).
- **No pairing-token/security changes** — nothing in `pairing_offer.py`, `models.py`'s token handling, or the compatibility gate was touched; `test_pairing_offer.py`'s 3 tests confirm unchanged behavior.
- **No new dependencies** — `requirements.txt` untouched; the fix uses only the `socket` module already imported by `lan_ip.py`.
- **No E4b work smuggled in** — no `pywin32` adapter-classification code, no Windows API calls, no interface-type discrimination logic. The design doc's Option C / 3b (deferred) is exactly what was *not* implemented here.

## Final classification

**`CANONICALIZED — LAN-IP SELECTION CORRECTNESS FIXED (E4A)`**

## Stop condition honored

E4b not started. Android retry architecture untouched. Bridge bind semantics untouched. Pairing/auth semantics untouched. Factory/Neural Empire lane untouched (out of scope for this project entirely). `preservation/pre-gate5f-dirty-2026-08-20` (stash and branch) not reapplied — reconfirmed via direct `git rev-parse` after the fast-forward, still `4f5b3488a965342fafb9e7be6b0fe8d754d27e6f`. All four rollback tags (`pre-salvage-e1-filter-nav`, `pre-salvage-e2-dialog-teardown`, `pre-salvage-e3-annotation-import`, `pre-salvage-e4a-lan-ip`) confirmed intact. The `fix/lan-ip-selection-e4a` branch was not pruned (still points at `45aac5f7...`, now also `master`'s tip). `master` not pushed to any remote.

## Final master SHA

```
45aac5f7c7a3d31187d27bbefc8f7efc491ae497
```
