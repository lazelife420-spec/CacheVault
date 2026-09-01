# Reality Gate

Tiered validation control plane for Cache Vault. Keeps the full canonical proof
but stops paying its full cost after every small change.

## Why

The canonical gate (`scripts/ci_local_full.ps1`) is authoritative — it rebuilds
the PyInstaller exe, runs the full suite, smoke-tests the packaged runtime, and
emits the custody/nonmutation proof. Running it after every edit is a ~60-minute
loop. Most changes do not need all of that.

Reality Gate splits validation into four tiers and routes each change to the
cheapest tier that still proves what matters. **The canonical gate is not
weakened** — you just stop invoking its full cost unless the change (or a release
checkpoint) actually requires it.

## Tiers

| Tier | ~Cost | What runs |
|------|-------|-----------|
| `fast` | 1–3 min | preflight · `compileall` · claim + secret tripwires · changed-module tests |
| `engineering` | 5–15 min | fast + safety spine (receipt/data) + `app.py --selftest` + focused smoke |
| `product` | 10–25 min | full pytest + selftest + all headless smokes + cross-component subsets (no packaging) |
| `canonical` | 45–70 min | delegates to `scripts/ci_local_full.ps1` **unchanged** (fresh build, packaged runtime smoke, custody proof) |

Tiers are cumulative; `canonical` stays the source of truth for release-grade
proof.

## Usage

```powershell
reality-gate status
reality-gate project list
reality-gate pipeline validate CacheVault --pipeline fast      # dry-run: show the plan
reality-gate run CacheVault --pipeline fast                     # execute
reality-gate run CacheVault                                     # defaults to engineering
reality-gate run CacheVault --pipeline canonical                # full expensive proof
reality-gate receipt verify <run-id>                            # tamper-evident receipt check
```

Install the console command with `pip install -e .[dev]` (provides
`reality-gate`). You can also run it without installing via
`python -m reality_gate ...`.

Optional short alias (documented only — never use `rg`, it collides with
ripgrep):

```powershell
Set-Alias rgate reality-gate
```

Scripts, receipts, docs, and automation MUST use the canonical `reality-gate`
name.

## Workflow

> fast while editing → engineering before commit → canonical at tranche
> closure / release-grade checkpoints.

## Change-aware selection (deterministic, checked-in)

`reality_gate/change_map.py` maps changed source files → required test lanes,
plus escalation rules. It is data expressed in Python (zero extra dependencies,
fully commented). Edit it to tune routing — no AI guessing.

Escalation ladder: `fast → engineering → product → canonical`. The selected tier
is a **floor**: escalation only raises the effective tier, never lowers it.

| Change | Routing |
|--------|---------|
| packaging-sensitive (`packaging/**`, `*.spec`, `requirements*.txt`, `pyproject.toml`, `app.py`, `build_meta.py`, bundled assets) | **force canonical** (packaging + packaged runtime must run) |
| gate/build tooling (`scripts/**`, `tools/**`, `.github/**`) | **force canonical** |
| orchestrator (`reality_gate/**`) | **force product** (broad suite) |
| shared test infra (`conftest.py`, `sandbox.py`, `tk_support.py`) | **force product** |
| mapped `cache_vault/**` source | run its lanes (no escalation) |
| unmapped `cache_vault/**` source (central/shared modules: `vault.py`, `models.py`, `settings.py`, `shell.py`, …) | **force product** (broad) — conservative |
| `tests/**` | run that test file (no escalation) |
| docs / non-bundled assets | fast tripwires only |

**Conservative by design:** uncertain / unmapped app-source changes escalate
upward (to product), and packaging/tooling changes escalate all the way to
canonical — never silently reducing coverage.

`--force-tier` pins a tier and disables escalation (loud warning); intended for
developing/validating Reality Gate itself, not for normal use.

## Receipts

Every run writes `reality_gate/runs/<run-id>.json` containing a `verdict` block
and a `verdict_hash` (sha256 over the canonical JSON of that block).
`reality-gate receipt verify <run-id>` recomputes the hash, so a tampered verdict
is detectable. Per-step logs live in `reality_gate/runs/logs/`.

## Phase 1 scope

This tranche delivers the four tiers + checked-in change-map. The canonical tier
reuses `scripts/ci_local_full.ps1` unchanged, so existing coverage semantics
remain authoritative. Deliberately deferred to later tranches:

- **Phase 2:** optimize the canonical gate internally without cutting coverage
  (parallelize isolation-safe tests, cache build inputs, shard long pytest
  groups, dedupe environment setup, avoid rebuilding identical artifacts) — with
  strict before/after coverage-equivalence evidence.
- **Later:** wire tiers into `.github/workflows/ci.yml`.

Do not optimize the canonical gate internals or modify GitHub Actions as part of
Phase 1.
