# Cache Vault — GitHub Pages landing

Sales surface for **Cache Vault Founder MVP v0.1.3**.

## Files

| File | Purpose |
|---|---|
| `docs/index.html` | Single-page landing (Free vs Founder, proof, download) |
| `docs/.nojekyll` | Disables Jekyll so GitHub Pages serves static HTML |

Source template: `cache_vault_github_pages_landing.zip` (integrated 2026-06-20).

## Live URLs

**Public landing (GitHub Pages — live):**

```text
https://z3r0dayzion-install.github.io/cache-vault-landing/
```

Repo: [github.com/Z3r0DayZion-install/cache-vault-landing](https://github.com/Z3r0DayZion-install/cache-vault-landing)

**In-repo copy** (`docs/index.html`) — Pages not enabled on the private CacheVault repo (plan limit). Use the public landing repo above for sales.

If CacheVault is made public or plan upgraded:

```text
https://Z3r0DayZion-install.github.io/CacheVault/
```

Enable on CacheVault:

```text
GitHub → Settings → Pages → Deploy from branch → master → /docs
```

**Dedicated landing repo** (live):

```powershell
pwsh scripts\deploy-github-pages-landing.ps1 `
  -Owner Z3r0DayZion-install `
  -Repo cache-vault-landing `
  -CheckoutUrl "https://your-checkout-url"
```

Live: https://z3r0dayzion-install.github.io/cache-vault-landing/

## Wired links

| Button | Current target |
|---|---|
| Download Free | [v0.1.3-founder-mvp release](https://github.com/Z3r0DayZion-install/CacheVault/releases/tag/v0.1.3-founder-mvp) |
| Buy Founder | [Gumroad checkout](https://cashdominion.gumroad.com/l/eojmeb) |

## Before first sale

1. Set checkout URL in `docs/index.html` (replace `href="#founder"` on Buy buttons) or redeploy with `-CheckoutUrl`.
2. Set app build env for in-app purchase link:
   ```powershell
   $env:FOUNDER_PURCHASE_URL = "https://your-checkout-url"
   ```
3. Verify release zip SHA256 on the page matches the published asset.

## Legacy

The minimal page at `landing/cache-vault-founder.html` is superseded by `docs/index.html`.
