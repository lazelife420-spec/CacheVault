# Cache Vault v0.1.0 - MVP

Cache Vault v0.1.0 is the first MVP release.

This release locks the teal vault-dial brand, ships the packaged Windows executable, and includes a reproducible asset pipeline with verification gates.

Cache Vault is a local Windows utility for keeping useful clipboard/cache items. It saves text clipboard entries locally, classifies them with smart filters, supports search and pinning, masks sensitive clips, and keeps everything off accounts, ads, telemetry, and cloud sync.

Proof:
- Commit: 8550a51
- Unit tests: 57 passing
- Asset verification: 12 required files present
- ICO: 16, 24, 32, 48, 128, 256 px
- Primary icon: teal only, no gold/cash edition pixels
- Window, tray, and exe icon verified against the finalized teal primary
- Gold cash edition is variant-only
- CI: GitHub Actions green for commit 8550a51

Artifacts:
- `CacheVault-v0.1.0-windows.zip`
- `SHA256SUMS.txt`
