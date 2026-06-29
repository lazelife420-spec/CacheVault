# Audit Report: Mobile + Image UI Audit (Chunk D1)

## Introduction
This document presents the findings of the Chunk D1 audit, focusing on the current implementation of mobile and image-related functionalities within the Cache Vault application. The primary goal of this audit is to map existing code paths, identify current behaviors, and highlight potential areas for improvement, particularly concerning the user experience (UX) for mobile and image interactions. This audit serves as a foundational step for subsequent UI polish and feature development.

## Current State Analysis

### 1. Current Desktop Image/Gallery Code Paths

The desktop image and gallery functionalities are primarily handled by three key files: `ui/clip_grid.py`, `ui/preview.py`, and `ui/shell.py`.

The `ui/clip_grid.py` file defines the `ClipGrid` class, which is responsible for rendering the metadata grid view of saved clips. It manages the display of clip attributes such as name, type, date added, last used date, source, favorite status, and proof hash. The rendering process is handled by the `render` and `render_batched` methods, which build and display rows of clips, utilizing batched rendering for improved performance. The class also manages single, multi, and range selection of clips, and allows sorting by various criteria. Visually, it employs `customtkinter` for UI elements, with styling defined in the `brand` and `theme` modules.

The `ui/preview.py` file implements the `PreviewPanel` class, serving as the right-hand preview, details, and actions panel for selected clips. For image handling, it utilizes `_image_frame` and `_image_label` to display image previews. The `_render_image_preview` method is responsible for loading and displaying image assets, including scaling and providing a fallback for unavailable images. Additionally, it displays image-related metadata and provides actions such as Copy Image, Drag PNG, Save As PNG, and Open Asset Folder.

The `ui/shell.py` file acts as the main desktop wiring layer, orchestrating various UI components and backend interactions. It initializes the mobile access bridge via the `_mobile_bridge.sync` call. The center panel wiring, managed by `_home`, `_list`, and `_grid`, is responsible for displaying the main content, including the `HomeDashboard`, `ClipList`, and `ClipGrid`. The file also defines callbacks for actions related to assets, such as loading, saving, and opening, and handles clipboard ingest, including image-vs-text save paths.

### 2. Current Mobile Bridge Endpoints

The mobile bridge functionality is implemented in `core/mobile/bridge.py` and `core/mobile/api.py`.

The `core/mobile/bridge.py` file implements the `MobileBridge` class, which acts as a read-only HTTP API for paired Android devices. It handles incoming requests and dispatches them to appropriate handlers. Key endpoints include `/mobile/v1/status`, which returns the status of the mobile API; `/mobile/v1/clips`, which lists all clips; and `/mobile/v1/clips/{id}`, which retrieves details for a specific clip. Crucially for image display on mobile devices, the `/mobile/v1/clips/{id}/asset` endpoint retrieves the binary asset for an image clip. Other endpoints include `/mobile/v1/search` for searching clips, and `/mobile/v1/collections`, `/mobile/v1/favorites`, and `/mobile/v1/recently-removed` for listing clips based on specific filters. The `/mobile/v1/inbox` endpoint lists clips originating from the mobile inbox. The `/mobile/v1/inbox/send` endpoint handles incoming mobile sends (text or image) from paired devices, representing a write operation. Finally, receipt POST routes such as `/mobile/v1/clips/{id}/copy`, `/mobile/v1/clips/{id}/share`, and `/mobile/v1/clips/{id}/save` log mobile copy, share, and save events without modifying vault state.

The `core/mobile/api.py` file defines the route table and clip serialization logic for the mobile API. It categorizes routes into `READ_ONLY_ROUTES`, `RECEIPT_POST_ROUTES`, and `INBOX_POST_ROUTES`, and includes the `clip_to_api` function for serializing clip data for mobile clients.

### 3. Current Android/Mobile Code Paths

The core logic for capturing and managing clips, including mobile-specific capture paths, is located in `core/vault.py`.

The `capture_mobile_share` method handles intentional paired mobile sends of text or URLs. It creates a new `Clip` with `capture_mode=models.CAPTURE_MOBILE_SHARE`, generates a preview, and records capture receipts and events. The `capture_mobile_image_share` method mirrors this functionality for image sends. It stores the image as a binary asset, creates an image clip with a non-revealing label, and records receipts and events. This method is the primary mechanism for phone-to-PC image transfer. The `list_mobile_inbox` method retrieves clips that were captured via `CAPTURE_MOBILE_SHARE`.

### 4. Current PC-to-Phone Save Behavior

Based on the audit of `core/mobile/bridge.py` and `core/mobile/api.py`, the mobile bridge primarily exposes read-only GET routes, with the exception of `INBOX_POST_ROUTES` for mobile-to-PC sends and `RECEIPT_POST_ROUTES` for logging actions. There is no explicit PC-to-phone save behavior implemented in the current API. The mobile device can retrieve assets via the `/mobile/v1/clips/{id}/asset` endpoint, but there is no mechanism for the PC to push or save files directly to the phone's local storage.

### 5. Current Phone-to-PC Receive Behavior

The phone-to-PC receive behavior is handled by the `/mobile/v1/inbox/send` endpoint in `core/mobile/bridge.py`, which dispatches to `_dispatch_inbox_post`. This endpoint processes incoming payloads and utilizes the `capture_mobile_share` and `capture_mobile_image_share` methods in `core/vault.py` to store the received content. Text and URLs are stored as standard clips, while images are stored as binary assets with corresponding image clips. All items received via this path are assigned the `CAPTURE_MOBILE_SHARE` capture mode, placing them in the Mobile Inbox.

### 6. Current Image Cache/Local Storage Behavior

Image storage is managed by the `VaultStorage` class, with specific logic for image assets detailed in `core/vault.py` and `core/image_assets.py`. When an image is captured (either via desktop screenshot or mobile share), it is stored as a binary asset on disk. A corresponding `Clip` record is created in the database, containing metadata and a reference to the asset. The `capture_image` and `capture_mobile_image_share` methods in `core/vault.py` demonstrate this process, creating a `ClipAssetRecord` and saving the binary data using `storage.save_clip_asset`. The `ui/preview.py` file retrieves these assets for display using `storage.load_clip_asset_bytes`.

### 7. Where Mobile Inbox / From Phone Should Land

Currently, items received from the phone are assigned the `CAPTURE_MOBILE_SHARE` capture mode. The `list_mobile_inbox` method in `core/vault.py` retrieves these items. In the UI, `ui/vault_screens.py` contains a `Mobile Inbox` screen that renders these inbound mobile clips. For the upcoming UI polish, the "Mobile Inbox" or "From Phone" section should be prominently integrated into the main navigation or dashboard, likely as a distinct filter or tab within the `HomeDashboard` or `FilterNav` components in `ui/shell.py`, ensuring easy access to items transferred from the paired device.

### 8. Smallest Safe First UI Polish Patch (Chunk D2 Plan)

The smallest safe first UI polish patch (Chunk D2) should focus on improving the desktop image viewer and gallery experience without altering the underlying data models or mobile bridge logic. This provides a fast visual win while maintaining stability.

**Proposed D2 Implementation Plan:**

| Component | Target File | Proposed Changes |
| :--- | :--- | :--- |
| **Image Grid Spacing** | `ui/clip_grid.py` | Adjust padding and margins within the `ClipGrid` rendering logic to provide better spacing between image thumbnails. |
| **Larger Thumbnails** | `ui/clip_grid.py`, `ui/preview.py` | Increase the default size of image thumbnails in the grid view and potentially adjust the scaling logic in `_render_image_preview`. |
| **Date-Group Headers** | `ui/clip_grid.py` | Implement logic to group clips by date (e.g., "Today", "Yesterday", "Jun 27") and render headers above each group in the grid view. |
| **Human Timestamps** | `ui/clip_grid.py`, `ui/preview.py` | Update the timestamp formatting logic (e.g., `_short` function) to display human-readable times (e.g., "Today · 1:24 PM"). |
| **Source/Status Badges** | `ui/clip_grid.py`, `ui/preview.py` | Add visual badges to indicate the source or status of a clip (e.g., "On PC", "From Phone", "Saved to Phone", "Proof Recorded"). This will require checking the `capture_mode` and other metadata. |
| **Empty/Loading/Error States** | `ui/clip_grid.py`, `ui/preview.py` | Refine the visual presentation of empty states (e.g., no clips match filter), loading states (if applicable), and error states (e.g., image asset unavailable). |
| **Data-Backed Claims** | `ui/preview.py` | Ensure that any claims about phone or local status are strictly backed by data (e.g., checking `clip_has_asset` before displaying "On PC"). |

This plan focuses entirely on the desktop UI presentation layer, specifically targeting `ui/clip_grid.py` and `ui/preview.py`, ensuring a safe and isolated update for the image gallery polish.
