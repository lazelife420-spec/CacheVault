# Cache Vault UI Consistency Audit

Date: 2026-07-01
Baseline: Settings Hub (`cache_vault/ui/settings_hub.py`) is the visual target.
Scope: v0.1.5-rc2. Recommend small, rc2-safe polish only. No full redesign.

## Why Settings Hub reads as the baseline

From `settings_hub.py` the pattern is:
- Left category nav (220px), one large page title (`CTkFont size=24 bold`).
- Grouped "cards": `CTkFrame(fg_color=brand.ROW_BG, corner_radius=12)` with an
  inner transparent frame padded `padx=20, pady=15`.
- Group section headers: `size=11 bold`, UPPERCASE, `brand.MUTED_FG`.
- Field rows: bold label (`size=14`) + muted description (`size=12`) on the left,
  control on the right. Generous `pady=8` between rows.
- Clear footer actions (Save / Cancel) using `theme.primary_button()` /
  `secondary_button()`.

The rest of the app mixes an older token set: `theme.vault_card()` uses
`fg_color=brand.SURFACE_BG, corner_radius=8, border_width=1`, and section
headings via `theme.section_heading()` are `STAMP_GOLD size=12`. So the two
biggest global mismatches are **card radius/fill (8/SURFACE_BG vs 12/ROW_BG)**
and **section-header style (gold 12 vs muted-11-uppercase)**, plus denser
spacing.

## Recommended shared tokens (define once, adopt gradually)

To avoid a risky global refactor, add helpers alongside the existing ones in
`theme.py` and adopt them per screen as each is touched:
- `hub_card()` = `fg_color=brand.ROW_BG, corner_radius=12` (matches Settings Hub).
- `hub_section_label()` = `size=11 bold uppercase, brand.MUTED_FG`.
- Standard inner padding `padx=20, pady=15` and row spacing `pady=8`.

Do not rip out `vault_card()`; leave it until each screen is intentionally
migrated.

## Per-screen findings

Format: current mismatch | should match | risky change to avoid | rc2-safe polish.

### Command Center / main dashboard (`home_dashboard.py`, `command_center.py`)
- Mismatch: title size matches (24 bold), but sections use `_section_title`
  gold headers, cards use `vault_card` (radius 8, SURFACE_BG), and labels are
  small/dense compared to Hub.
- Should match: card radius/fill, muted-uppercase section labels, more spacing
  between cards and rows.
- Avoid: restructuring `render()` order or the multi-select/batch-toolbar logic
  (recently stabilized; touching it risks re-introducing the selection loop).
- rc2-safe: bump inter-card `pady`, switch section headers to the Hub style,
  align card radius to 12. Visual-only, no layout/state changes.

### Mobile Access screen (`vault_screens.py`, `mobile_dialogs.py`)
- Mismatch: too technical (raw host/port/IP/Connection Doctor text), dense.
- Should match: "Connect phone" language, a single primary action, technical
  detail collapsed under Advanced (pattern already exists in the pair dialog).
- Avoid: changing bridge enable/disable wiring or the pairing token logic.
- rc2-safe: relabel to plain-language, promote one primary button, demote raw
  IP/port to an Advanced block. Copy-only + button emphasis.

### Screenshots / Images view (`clip_grid.py`, `clip_list.py`, `filters.py`)
- Mismatch: bulk export actions are hidden until multi-select; no persistent
  toolbar; card styling differs from Hub.
- Should match: visible bulk actions (see the Screenshots Bulk Workflow audit).
- Avoid: changing asset storage/preview lifecycle.
- rc2-safe: surface an "Export Screenshots to Folder..." entry and align spacing.

### Context menus (`clip_context.py`, `core/contextmenu.py`)
- Mismatch: menus include dead/no-op entries (e.g. "View Proof" is a no-op;
  some items disabled) which erodes trust.
- Should match: only useful, implemented actions enabled.
- Avoid: reworking the menu-building or dispatch structure broadly.
- rc2-safe: remove/hide the no-op items; keep only implemented actions.

### Pair Device dialog (`mobile_dialogs.py` `PairAndroidDialog`)
- Mismatch: token/host/port shown as a text block; manual-first; no QR.
- Should match: QR-first with manual under Advanced (see QR flow plan).
- Avoid: implementing QR end to end in rc2 (phone can't scan yet).
- rc2-safe: tighten copy, keep token hidden by default, add screenshot-safe
  hiding of the token region.

### Quick Paste (`quick_paste.py`)
- Mismatch: compact overlay with its own styling; acceptable as a HUD but fonts
  differ.
- Should match: font sizes and accent colors only.
- Avoid: changing the paste-delivery/focus logic.
- rc2-safe: align font/accent tokens; no behavior change.

### Capture Rules (`dialogs.py`, `core/capture_rules.py`)
- Mismatch: form-dense dialog, older card/section styling.
- Should match: Hub card + section-header style, more row spacing.
- Avoid: changing rule evaluation/schema.
- rc2-safe: restyle containers and section labels only.

### Stamped Receipts (`receipt_ledger.py`, `mobile_dialogs.py` receipts view)
- Mismatch: monospace text-dump ledger; readable but visually off-baseline.
- Should match: Hub card framing and section header for the list container.
- Avoid: changing receipt data or proof rendering.
- rc2-safe: wrap the ledger in a Hub-style card; keep mono font for values.

## rc2 recommendation

Ship only visual-only polish this cycle: (1) unify section-header style, (2)
align card radius/fill to the Hub, (3) increase spacing on the dashboard, (4)
remove dead context-menu items, (5) plain-language + Advanced-collapse on Mobile
Access. Defer all structural/layout rewrites and the QR pair dialog rebuild.
