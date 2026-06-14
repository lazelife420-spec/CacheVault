# Cache Vault v0.1.2

Cache Vault v0.1.2 hardens the Windows packaging trust surface without
changing product scope.

Planned highlights:
- Windows file version and product metadata in the packaged exe
- Version consistency across source, packaging metadata, README, and release notes
- Exe metadata verification in local packaging checks and the release workflow
- Clean-machine smoke checklist for extract, launch, tray, hotkey, startup, data path, and cleanup
- Code-signing plan documented with no false SmartScreen trust claims
