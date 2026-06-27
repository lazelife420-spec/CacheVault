# Cache Vault — GitHub Pages landing

Sales surface for **Cache Vault v0.1.4**.

## Files

| File | Purpose |
|---|---|
| `docs/index.html` | Single-page landing (Free vs Founder, proof, download) |
| `docs/docs.html` | Install & user guide (rendered from README) |
| `docs/changelog.html` | Release notes (rendered from CHANGELOG.md) |
| `docs/.nojekyll` | Disables Jekyll so GitHub Pages serves static HTML |

`index.html` canonical/OG URLs point at the live host `https://lazelife420-spec.github.io/CacheVault/`. `docs.html` and `changelog.html` are linked from the landing nav and footer.

Source template: `cache_vault_github_pages_landing.zip` (integrated 2026-06-20).

## Live URLs

**Public landing (GitHub Pages — live):**

```text
https://lazelife420-spec.github.io/CacheVault/
```

Repo: [github.com/lazelife420-spec/CacheVault](https://github.com/lazelife420-spec/CacheVault)

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

Live: https://lazelife420-spec.github.io/CacheVault/

## Wired links

| Button | Current target |
|---|---|
| Download Free | [v0.1.4 release](https://github.com/lazelife420-spec/CacheVault/releases/tag/v0.1.4) |
| Buy Founder | [Gumroad checkout](https://cashdominion.gumroad.com/l/eojmeb) |

## Before first sale

1. Set checkout URL in `docs/index.html` (replace `href="#founder"` on Buy buttons) or redeploy with `-CheckoutUrl`.
2. Set app build env for in-app purchase link:
   ```powershell
   $env:FOUNDER_PURCHASE_URL = "https://your-checkout-url"
   ```
3. Verify release zip SHA256 on the page matches the published asset.
   v0.1.4 ZIP SHA256: `07d6049153c5f4fd980990099a27062ffce5304fe8d5c73a41fbbb0d6874fa4a`

## Legacy

The minimal page at `landing/cache-vault-founder.html` is superseded by `docs/index.html`.
