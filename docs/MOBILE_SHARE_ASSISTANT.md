# Cache Vault Mobile Share Assistant

**Product name in UI:** Cache Vault Mobile / ShareSafe  
**Simple Mode:** respectful, large-button flow for anyone — not labeled “old person mode.”  
**Power Mode:** full Safe, receipt, and bridge controls for advanced users.

## What it is

The mobile Share Assistant lets you **intentionally** send webpage content, links, or text from your phone to a **paired** Cache Vault desktop over the local network. This is **not cloud sync**. It is **Send-to-PC** with receipts.

```
Browser / app → Android Share → Cache Vault Mobile → Simple Mode
  → Send to PC → choose Safe (if needed) → desktop Mobile Inbox → receipt stamped
```

## Simple Mode

**User-facing name:** Simple Mode (alternate: Family Mode — not used in UI yet)

### Screen: What do you want to do?

Large, high-contrast buttons:

| Action | What happens |
|--------|----------------|
| **Send to PC** | Requires pairing. Item lands in desktop **Mobile Inbox**. Receipt stamped. |
| **Save Link** | Saves link locally on phone flow (when implemented end-to-end). |
| **Copy Text** | Copies clean text to phone clipboard — explicit user action only. |
| **Save to Vault** | Saves through paired bridge when connected. |
| **Share with Someone** | Opens Android share sheet with content you chose. |
| **Read Aloud** | Planned — system text-to-speech, optional later. |
| **Open Later** | Placeholder for read-later list — not in first slice. |

### Send-to-PC flow (Simple Mode)

1. User taps **Send to PC**
2. Shows pairing status: `Connected to Christian's PC` or `Not connected`
3. Default Safe used unless user picks one (Links, Family, Temporary, etc.)
4. Desktop receives item in **Mobile Inbox**
5. Mobile shows: `Sent to PC` · `Saved in Links Safe` · `Receipt stamped`

### Status messages (plain language)

- Saved
- Sent to PC
- Copied
- Not saved
- Could not send

## Power Mode

Separate from Simple Mode. Shows:

- Safe picker
- Tags / source URL
- Source app
- Receipt details
- Hash / proof status
- Bridge status
- Export / proof metadata

## Desktop Mobile Inbox

Sidebar: **Mobile Inbox** / **Incoming from Phone**

Each item shows:

- Preview
- Source app / device
- URL / domain
- Safe
- Receipt status
- Received time

Actions (implemented):

- Open on PC
- Copy to PC Clipboard
- Open Link (links only)
- Export Proof Zip
- View Receipt
- Remove from History

## API (paired write)

`POST /mobile/v1/inbox/send`

Headers: `X-Device-Id`, `Authorization: Bearer <token>`

Body:

```json
{
  "item_type": "text",
  "content": "shared text or URL",
  "source_app": "Chrome",
  "source_device_name": "Pixel 8",
  "source_url": "https://example.com/article",
  "safe_id": "links",
  "user_action": "send_to_pc"
}
```

Response:

```json
{
  "success": true,
  "desktop_item_id": "<clip-id>",
  "receipt_id": "<clip-id>",
  "safe_id": "links",
  "safe_name": "Links"
}
```

`GET /mobile/v1/inbox` — list items with `capture_mode: mobile_share` (masked like other list routes).

## Receipt fields

Desktop stamps (metadata only — **no full sensitive content**):

| Action | When |
|--------|------|
| `mobile_sent_to_pc` | Vault item created from phone send |
| `mobile_inbox_received` | Inbox receive confirmation |

Receipts include: `clip_id`, `safe_id`, `safe_name`, `capture_mode`, `source_app`, content **hash**, `item_type`, timestamp.

## Safety / privacy boundaries

| Rule | Status |
|------|--------|
| Requires existing pairing token | **Yes** |
| No silent clipboard spying | **Yes** — explicit Share / button only |
| No cloud dependency | **Yes** — LAN paired bridge |
| No unauthenticated writes | **Yes** |
| Mobile cannot mutate desktop originals | **Yes** |
| Mobile cannot delete/edit desktop items | **Yes** |
| No encryption claim unless implemented | **Yes** — Safes are not encrypted |
| Sensitive-looking content | **Yes** — phone warns and requires confirm before Send to PC (`SensitiveText` + confirm dialog); desktop still masks on receipt |

## Android Share Sheet

`ShareAssistantActivity` handles `ACTION_SEND` for `text/plain` **and `image/*`** and
opens **Simple Mode** with the shared content pre-filled.

Entry: Android Share → Cache Vault Mobile → giant buttons → **Send to PC** → done.

### Image send

Shared images (`image/*`, up to 10 MB) are read from the content URI, base64-encoded,
and sent to `POST /mobile/v1/inbox/send` with `item_type=image`. The desktop verifies the
bytes are a real image (Pillow), stores them as an image clip + binary asset in the
Default Safe, and stamps a receipt. Receipts never contain the image bytes. The phone
shows the filename/size before sending; the desktop applies the same vault-lock guards to
mobile images as any other clip.

## Known limitations (first slice)

- File (non-image) send deferred — `image/*` only for now
- Read Aloud not implemented yet
- Open Later not implemented
- Simple Mode Safe picker uses default Safe unless Power Mode expanded
- No iOS companion

## Regression

Existing read-only routes must keep working:

- `GET /mobile/v1/status`
- `GET /mobile/v1/clips`
- `GET /mobile/v1/recently-removed`

Safe metadata (`safe_id`, `safe_name`, `capture_mode`) remains in mobile clip payloads.
