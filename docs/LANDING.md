# Cache Vault — GitHub Pages landing

Sales surface for **Cache Vault Founder MVP v0.1.3**.

## Files

| File | Purpose |
|---|---|
| `docs/index.html` | Single-page landing (Free vs Founder, proof, download) |
| `docs/.nojekyll` | Disables Jekyll so GitHub Pages serves static HTML |

Source template: `cache_vault_github_pages_landing.zip` (integrated 2026-06-20).

## Live URLs (after Pages is enabled)

**In-repo Pages** (recommended):

```text
https://Z3r0DayZion-install.github.io/CacheVault/
```

Enable:

```text
GitHub → Settings → Pages → Deploy from branch → master → /docs
```

**Dedicated landing repo** (optional):

```powershell
pwsh scripts\deploy-github-pages-landing.ps1 `
  -Owner Z3r0DayZion-install `
  -Repo cache-vault-landing `
  -CheckoutUrl "https://your-checkout-url"
```

## Wired links

| Button | Current target |
|---|---|
| Download Free | [v0.1.3-founder-mvp release](https://github.com/Z3r0DayZion-install/CacheVault/releases/tag/v0.1.3-founder-mvp) |
| Buy Founder | `#founder` (placeholder — replace with checkout URL) |

## Before first sale

1. Set checkout URL in `docs/index.html` (replace `href="#founder"` on Buy buttons) or redeploy with `-CheckoutUrl`.
2. Set app build env for in-app purchase link:
   ```powershell
   $env:FOUNDER_PURCHASE_URL = "https://your-checkout-url"
   ```
3. Verify release zip SHA256 on the page matches the published asset.

## Legacy

The minimal page at `landing/cache-vault-founder.html` is superseded by `docs/index.html`.
