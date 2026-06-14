# Windows Code-Signing Plan

Cache Vault is not code-signed yet. This plan documents the realistic next
step without pretending SmartScreen is solved before it is.

## Certificate options

- Azure Artifact Signing: Microsoft's recommended option for non-Store Windows app distribution. See [Code signing options for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options).
- OV code-signing certificate from a public CA: practical fallback when Azure Artifact Signing is unavailable for the publisher's region or procurement path.
- EV code-signing certificate: can still matter for procurement or enterprise policy, but Microsoft now documents that EV no longer provides an automatic SmartScreen bypass.

## Expected SmartScreen reality

- Signed binaries can still show SmartScreen warnings when the file hash has little or no reputation.
- Microsoft documents SmartScreen as a reputation-based system for apps and downloaded files. See [Microsoft Defender SmartScreen overview](https://learn.microsoft.com/en-us/windows/security/operating-system-security/virus-and-threat-protection/microsoft-defender-smartscreen/).
- Microsoft's current Windows app distribution guidance says SmartScreen reputation is hash-based and builds over time for new files. See [SmartScreen reputation for Windows app developers](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).
- EV certificates are no longer an instant bypass according to Microsoft's current guidance.

## What changes once Cache Vault is signed

- Windows can show a verified publisher instead of an unknown publisher when the signature chain is trusted.
- The signature proves the binary has not been modified after signing.
- A timestamped signature can remain valid after the signing certificate expires.
- Enterprise allow-listing and internal deployment reviews usually become easier because the binary has a stable publisher identity.

## What signing does not solve

- It does not guarantee zero SmartScreen warnings for a new public binary.
- It does not transfer reputation automatically to every new file hash.
- It does not let us make "Microsoft trusted" or "warning-free" claims.
- It does not retroactively fix already-published unsigned artifacts without changing the file hash and reissuing the release assets.

## Practical signing plan

1. Keep the Windows version/product metadata stable and truthful before signing.
2. Pick one publisher identity and keep it consistent across future releases.
3. Choose Azure Artifact Signing if eligible; otherwise choose a conventional OV certificate from a trusted CA.
4. Sign the final packaged exe with SHA-256 and RFC 3161 timestamping.
5. Verify the signature on a clean Windows machine before publishing.
6. Keep the same signing identity across releases so reputation can accumulate as much as Microsoft's model allows.
