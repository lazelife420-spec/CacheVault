# Cache Vault Founder licenses

Founder Edition uses **offline signed license files**. The app embeds only the
**public key**; the **private signing key never belongs in the repository**.

## Generate a signing keypair (once)

```powershell
python tools\generate_founder_license.py --generate-keypair --out-dir C:\secure\cachevault-keys
```

Keep `cachevault_founder_private.pem` outside the repo and back it up securely.
Embed `cachevault_founder_public.pem` in `cache_vault/licensing.py` for release
builds that should verify your production licenses.

## Issue a license after manual payment

```powershell
python tools\generate_founder_license.py `
  --licensee buyer@example.com `
  --edition founder `
  --private-key C:\secure\cachevault-keys\cachevault_founder_private.pem `
  --out C:\licenses\buyer-cachevault-founder-license.json
```

Send the buyer:

1. Download link for the app package
2. The `license.json` file (or paste contents)
3. Instructions: **Founder** screen → **Import License File** or **Enter License**

## License file location (installed)

```text
%LOCALAPPDATA%\CacheVault\license.json
```

## License states

| State | Meaning |
|---|---|
| `MISSING_LICENSE` | Free edition |
| `FOUNDER_VALID` | Founder features unlocked |
| `INVALID_SIGNATURE` | Rejected |
| `WRONG_PRODUCT` | Not a Cache Vault license |
| `CORRUPT_LICENSE` | Unreadable or malformed |
| `EXPIRED_LICENSE` | Past `expires_at` |

Lifetime Founder licenses use `"expires_at": null`.

## Founder feature keys

```text
exports_advanced
zip_export
proof_pack_export
html_bundle_export
editable_copies_advanced
smart_filters_advanced
macros_advanced
safes_advanced
```

See `docs/CACHE_VAULT_FREE_VS_FOUNDER.md` for the public matrix.
