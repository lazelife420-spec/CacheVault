# Cache Vault — First Sale Runbook

You are at the seller stage. No new features until first purchase works end-to-end.

## Live surfaces

| Surface | URL |
|---|---|
| Landing | https://z3r0dayzion-install.github.io/cache-vault-landing/ |
| Release | https://github.com/Z3r0DayZion-install/CacheVault/releases/tag/v0.1.3-founder-mvp.2 |
| Landing repo | https://github.com/Z3r0DayZion-install/cache-vault-landing |

## Path map

```text
Landing → Download Free → GitHub Release → ZIP
Landing → Buy Founder   → checkout URL (wire next)
App     → Founder       → import license.json
```

## 1. Create checkout (you, ~15 min)

Fastest options for a $19 one-time Founder license:

| Provider | Why |
|---|---|
| [Gumroad](https://gumroad.com) | Fastest MVP, file delivery + email |
| [Lemon Squeezy](https://lemonsqueezy.com) | License keys optional, clean checkout |
| [Stripe Payment Link](https://stripe.com/payments/payment-links) | Minimal if you already have Stripe |

### Product copy (paste as-is)

**Title:**

```text
Cache Vault Founder Edition — One-Time Founder License
```

**Description:**

```text
A one-time Founder license for Cache Vault. Unlocks advanced exports, proof packs, HTML bundles, smart organization, macros, custom safes, and Founder-track updates. Cache Vault is local-first: no account, no cloud requirement, and no subscription.
```

**Price:** `$19 USD`

**Delivery note (confirmation email / product page):**

```text
After purchase, you receive a Founder license file and install/import instructions. Licenses are manually issued during the Founder MVP period.
```

**Buyer instructions (send with license file):**

1. Download Cache Vault from the GitHub release linked on the landing page.
2. Open Cache Vault → sidebar **Founder** → **Import License File**.
3. Select the attached `license.json`. Restart if prompted.

## 2. Redeploy landing with checkout URL

After you have the checkout link:

```powershell
pwsh scripts\deploy-github-pages-landing.ps1 `
  -Owner Z3r0DayZion-install `
  -Repo cache-vault-landing `
  -CheckoutUrl "https://YOUR-CHECKOUT-URL"
```

Also update `docs/index.html` Buy button hrefs and commit to CacheVault.

## 3. Set in-app purchase URL (next app build)

**Checkout (live):** https://cashdominion.gumroad.com/l/eojmeb

```powershell
$env:FOUNDER_PURCHASE_URL = "https://cashdominion.gumroad.com/l/eojmeb"
pwsh packaging\build_exe.ps1
pwsh packaging\package_release.ps1 -Tag v0.1.3-founder-mvp.2
```

Rebuild release only if you need **Copy Purchase Link** in the app to match checkout.

## 4. Issue a license after payment

```powershell
python tools\generate_founder_license.py `
  --licensee buyer@example.com `
  --private-key C:\secure\cachevault-keys\cachevault_founder_private.pem `
  --out C:\secure\licenses\buyer-founder-license.json
```

Email: ZIP download link + `license.json` + install steps above.

## 5. Buyer simulation (run before strangers buy)

```powershell
pwsh scripts\buyer_simulation.ps1
```

Manual UI checks (5 min):

- [ ] Open landing → Download Free → ZIP downloads
- [ ] Extract → run `CacheVault.exe` → Free mode usable
- [ ] Sidebar **Founder** opens
- [ ] Locked export shows upgrade prompt
- [ ] Import test license → Founder active after restart
- [ ] Export proof receipt — no clipboard contents in output
- [ ] Buy Founder on landing opens real checkout (after step 2)

## 6. Post the link

When simulation passes, post:

```text
Cache Vault Founder MVP — local-first clipboard vault for Windows.
Free tier is usable. Founder unlocks proof/export power tools.
https://z3r0dayzion-install.github.io/cache-vault-landing/
```

## Do not

- Add features before first sale
- Redesign the landing page
- Start another app
- Claim cloud, mobile, or AI

Your next win is one person clicking Buy.
