# Cache Vault — Feature Direction

> One local database. Saved clips, organization, and clean export.
> Multi-vault switching is **out of scope** for this phase.

## Core concepts

### 1. History / New Clips

- Normal clipboard history — everything captured from the clipboard.
- Consecutive duplicates are collapsed (not re-captured).
- Sensitive clips are masked and auto-expire per settings.
- **Pruning:** Settings → *History limit* (`history_max_clips`). When the live
  clip count exceeds the limit, the **oldest non-favorite** clips are moved to
  **Recently Removed** (soft delete, restorable). `0` = unlimited.
- Favorites are **never** pruned by history limit.

### 2. Favorites / Saved Clips

- User-marked important clips (stored in `is_pinned`; UI says *Favorites*).
- Float to the top of lists (`ORDER BY is_pinned DESC, created_at DESC`).
- Survive history pruning and persist across restarts.
- Right-click or preview panel: **Add to Favorites** / **Remove from Favorites**.

### 3. Collections / Folders

- Virtual app folders inside the single Cache Vault database — **not** separate
  vault databases.
- One collection per clip (multi-tagging deferred).
- Examples: Work, Code, Receipts, Links, Notes.
- Sidebar shows a dynamic **Collections** section (`col:{name}` filter keys).
- **Move to Collection…** dialog: pick existing or type a new name; remove from
  collection clears the field.

### 4. Recently Removed

- **Remove from History** soft-deletes a clip (`deleted_at` set).
- Clips land here first; user can **Restore** or **Permanently Remove**.
- Content is preserved until permanent removal (unlike *Expired* sensitive clips).
- **Never** deletes, moves, or modifies real files/folders on disk.

## Right-click clip row menu

| Action | When |
|--------|------|
| Copy Again | Always |
| Add to / Remove from Favorites | Live clips |
| Move to Collection… | Live clips |
| Export / Save As… | Live clips |
| Open | Valid local file/folder path that exists |
| Reveal in Explorer | Valid local path (parent folder if target missing) |
| Remove from History | Live clips |
| Restore | Recently Removed |
| Permanently Remove | Recently Removed |

Menu logic lives in `cache_vault/core/contextmenu.py` (UI-free, unit-tested).

## Export / Save As

### Single clip

Save as `.txt`, `.md`, `.html`, or `.json` (JSON includes full metadata).

### Multiple clips or a collection

Export as an **organized folder** or **zip archive** with:

```
index.html      — human-readable export browser
manifest.json   — machine-readable metadata
clips/          — one text file per clip
files/          — optional file copies (only when opted in)
```

### File safety (non-negotiable)

- Default export of file/folder path clips: **path reference + metadata only**.
- Real files copied into `files/` **only** when user checks *Include file copies*.
- **Never** delete, move, or modify originals on disk.
- **Never** execute clip contents.
- URLs are not opened automatically from unsafe text; Open/Reveal only for
  clearly-local Windows paths (`pathutil`).

### Metadata preserved on export

| Field | Source |
|-------|--------|
| Clip ID | `clip.id` |
| Name/preview | `clip.preview` |
| Full content or reference | `clip.content` + `is_reference` |
| Format/type | `content_type`, `classification` |
| Size | byte length of content |
| Date added | `created_at` |
| Date used | `updated_at` |
| Source app/window | `source_app`, `source_window` |
| Favorite state | `is_pinned` → `is_favorite` |
| Collection name | `collection` |
| Export timestamp | set at export time |
| Cache Vault version | package `__version__` |

## UI

### Sidebar sections

Primary organization (plus smart-type filters for discovery):

- **All Clips**
- **Favorites**
- **Collections** (dynamic)
- **Recently Removed**

Also: Links, Files/Paths, Code, Commands, Emails, Phone numbers, Sensitive,
Duplicates, Today, This Week, Expired.

### Search

- Placeholder: *Search everything…*
- When the search box has text, search runs **across all clips** — live history
  **and** Recently Removed (not Expired sensitive stubs).
- Structured tokens: `type:`, `source:`, `sensitive:`, `pinned:`.
- Without search text, the active sidebar filter applies.

### Preview pane

Shows selected clip content and metadata: type, source, added, last used,
favorite, collection, removed/expiry when relevant.

Action buttons match context-menu capabilities (including Restore /
Permanently Remove for deleted clips).

### Export control

Top bar button: **Export / Save As** (not “Import Vault”). Exports the clips
currently shown (active filter/collection + search). Per-clip export via
right-click menu.

## Database

- Single SQLite file: `%LOCALAPPDATA%\CacheVault\cache_vault.db`
- Incremental column migration on open — existing history is **never** reset.
- `collection` column on clips; no separate collections table yet.

## Scope limits (this phase)

| In scope | Deferred |
|----------|----------|
| One Cache Vault DB | Multi-vault switching |
| Favorites, collections, Recently Removed | Multi-tag per clip |
| Export folder + zip | Import from export |
| History pruning (settings) | Auto-purge Recently Removed after N days |
| Right-click on clip rows | Global right-click hijack |
| Safe path Open/Reveal | Bulk collection rename/delete UI |
| Column-add DB migration | Versioned migration table, FTS index |
| | Content encryption |
| | Release tag (unless explicitly approved) |

## Tests (required)

| Test | Module |
|------|--------|
| Favorite survives pruning | `test_favorites.py`, `test_pruning.py` |
| Clip moved into collection | `test_collections.py` |
| Collection persists after restart | `test_collections.py` |
| Export text clip as txt/md/html/json | `test_export.py` |
| Export collection as folder | `test_export.py` |
| Export collection as zip | `test_export.py` |
| Manifest contains metadata | `test_export.py` |
| Path clip export: no file copy by default | `test_export.py` |
| Include file copies: output only | `test_export.py` |
| Remove from History: disk untouched | `test_favorites.py`, `test_recently_removed.py` |
| Existing DB migrates safely | `test_migration.py` |
| Search across live + Recently Removed | `test_search.py` |

Run: `python -m pytest`
