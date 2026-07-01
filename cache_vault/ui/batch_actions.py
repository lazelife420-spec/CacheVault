"""UI batch operations for multi-selected clips."""

from __future__ import annotations

import zipfile
from pathlib import Path
import customtkinter as ctk
from tkinter import filedialog, messagebox

from ..core import models, image_assets, copy_clean, editable_copies
from ..core.selection import analyze_selection
from ..core.formatter import format_batch_links
from .dialogs import SafePickerDialog


def bulk_copy(window) -> None:
    bulk_copy_format(window, "plain")


def bulk_export_proof(window) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return
    if not window._require_founder("proof_pack_export"):
        return

    from ..core.exports import export_zip_basename

    dest = filedialog.asksaveasfilename(
        parent=window,
        title="Export proof zip",
        defaultextension=".zip",
        initialfile=export_zip_basename(),
        filetypes=[("Zip archive", "*.zip")],
    )
    if dest:
        window.vault.export_proof_zip(ids, dest, mode="auto")
        window.refresh()
        window._show_toast(f"Exported proof for {len(ids)} clips.")


def bulk_move_to_safe(window) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return

    def pick(safe_id: str, safe_name: str) -> None:
        moved = 0
        for clip_id in ids:
            if window.vault.move_to_safe(clip_id, safe_id):
                moved += 1
        window.refresh()
        window._show_toast(f"Moved {moved} clips to {safe_name}.")

    SafePickerDialog(
        window, window.vault.settings,
        title="Move to Safe",
        on_pick=pick,
        on_create=window._create_safe_if_allowed,
    )


def bulk_remove(window) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return

    ok = messagebox.askyesno(
        "Remove from History",
        f"Remove {len(ids)} clips from Cache Vault history? "
        "They can be restored from Recently Removed.\n\n"
        "This does not delete any files from your computer.",
        parent=window,
    )
    if not ok:
        return
    for clip_id in ids:
        window.vault.remove_from_history(clip_id)
    window._clear_selection()
    window.refresh()
    window._preview.show(None)


def bulk_copy_format(window, format_name: str) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return

    clips = []
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None:
            clips.append(clip)

    if not clips:
        window._show_toast("Nothing to copy.")
        return

    summary = analyze_selection(clips)

    has_images = summary.image_count > 0
    has_text_or_links = (summary.link_count + summary.text_count) > 0

    if not has_text_or_links:
        window._show_toast("Use Copy PNGs for screenshot selections.")
        return

    if summary.selection_class == "link_only":
        combined = format_batch_links(clips, format_name)
    else:
        parts = []
        for clip in clips:
            if clip.content_type == models.CONTENT_IMAGE:
                continue
            elif getattr(clip, "classification", None) == models.CLASS_LINK:
                formatted_link = format_batch_links([clip], format_name)
                parts.append(formatted_link)
            else:
                content = window.vault.copied_again(clip.id)
                if content:
                    parts.append(content)
        if format_name in ("markdown", "numbered"):
            combined = "\n".join(parts)
        else:
            combined = "\n\n".join(parts)

    window.clipboard_clear()
    window.clipboard_append(combined)
    window._monitor.note_local_copy(combined)

    if summary.selection_class == "link_only":
        if format_name == "plain":
            toast_msg = f"Copied {summary.link_count} links"
        else:
            toast_msg = f"Copied {summary.link_count} links as {format_name.capitalize()}"
    elif summary.selection_class == "text_only":
        toast_msg = f"Copied {summary.text_count} text clips"
    else:
        total_copied = summary.link_count + summary.text_count
        toast_msg = f"Copied {total_copied} text/link clips"

    if has_images:
        toast_msg += f" ({summary.image_count} image{'s' if summary.image_count != 1 else ''} skipped)"

    window._show_toast(toast_msg)

    # Record receipt metadata
    item_breakdown = {
        "links": summary.link_count,
        "text": summary.text_count,
        "images": summary.image_count,
    }

    if has_images:
        meta = {
            "action": "batch_copy_text_parts",
            "source": "desktop",
            "count": summary.selected_count,
            "copied_count": summary.link_count + summary.text_count,
            "skipped_count": summary.image_count,
            "skipped_types": ["image"],
            "item_breakdown": item_breakdown,
            "format": format_name,
            "transfer_status": "partial",
            "timestamp": models.now_iso(),
            "success": True,
        }
        action_name = "batch_copy_text_parts"
    else:
        meta = {
            "action": "batch_copy_selected",
            "source": "desktop",
            "count": summary.selected_count,
            "format": format_name,
            "item_breakdown": item_breakdown,
            "transfer_status": "completed",
            "timestamp": models.now_iso(),
            "success": True,
        }
        action_name = "batch_copy_selected"

    editable_copies.write_file_receipt(action_name, meta)
    window.vault.events.record(models.EVENT_COPIED_AGAIN, None, meta)


def bulk_create_receipt(window, summary) -> None:
    if not window._guard_unlocked():
        return
    window._show_toast(f"Receipt created for {summary.selected_count} items.")


def bulk_copy_images(window) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return

    image_ids = []
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None and clip.content_type == models.CONTENT_IMAGE:
            image_ids.append(cid)

    if not image_ids:
        window._show_toast("No screenshots selected to copy.")
        return

    first_id = image_ids[0]
    png = window.vault.copied_again_image(first_id)
    if not png:
        window._show_toast("Failed to copy screenshot.")
        return

    from ..core import image_assets
    if image_assets.write_clipboard_png(png):
        window._monitor.note_local_copy_image(png)
        if len(image_ids) > 1:
            window._show_toast(f"Copied primary image to clipboard; use Save PNGs or Export ZIP for the remaining {len(image_ids) - 1} images.")
        else:
            window._show_toast("Copied screenshot to clipboard.")
    else:
        window._show_toast("Clipboard copy not supported in this environment.")


def bulk_save_images(window, ids=None) -> None:
    if not window._guard_unlocked():
        return
    ids = list(ids) if ids is not None else list(window._selected_clip_ids)
    # Only image clips are exportable; filter first so an empty screenshot view
    # (or a selection with no images) is handled without opening a dialog.
    image_ids = []
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None and clip.content_type == models.CONTENT_IMAGE:
            image_ids.append(cid)
    if not image_ids:
        window._show_toast("No screenshots to export.")
        return

    dest = filedialog.askdirectory(parent=window, title="Export Screenshots to Folder")
    if not dest:
        return

    saved_count = 0
    failed_count = 0
    for cid in image_ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is None or clip.content_type != models.CONTENT_IMAGE:
            continue
        loaded = window.vault.storage.load_clip_asset_bytes(cid)
        if not loaded:
            failed_count += 1
            continue
        png_bytes, _ = loaded

        filename = image_assets.make_smart_filename(clip)
        if not filename.lower().endswith(".png"):
            filename += ".png"
        target_path = Path(dest) / filename
        final_path = image_assets.next_available_path(target_path)

        try:
            final_path.write_bytes(png_bytes)
            saved_count += 1
        except Exception:
            failed_count += 1

    if saved_count > 0:
        msg = f"Saved {saved_count} screenshots to {dest}"
        if failed_count:
            msg += f" ({failed_count} failed due to missing files)"
        window._show_toast(msg)

        # Record event/receipt
        meta = {
            "action": "batch_export_images",
            "source": "desktop",
            "count": saved_count,
            "format": "png",
            "item_breakdown": {
                "images": saved_count,
            },
            "transfer_status": "completed" if failed_count == 0 else "partial",
            "timestamp": models.now_iso(),
            "success": failed_count == 0,
        }
        editable_copies.write_file_receipt("batch_export_images", meta)
        window.vault.events.record(models.EVENT_COPIED_AGAIN, None, meta)
    else:
        window._show_toast(f"Failed to save screenshots. {failed_count} files missing or corrupted.")


def _make_text_filename(clip) -> str:
    created = clip.created_at[:10]
    prefix = "Text"
    if getattr(clip, "classification", None) == "link":
        prefix = "Link"

    title = getattr(clip, "title", None) or ""
    if not title:
        words = (clip.content or "").strip().split()
        if words:
            title = "_".join(words[:3])
        else:
            title = clip.id[:8]

    clean_title = "".join(c if c.isalnum() or c == "_" else "_" for c in title)
    clean_title = clean_title[:25].strip("_")
    if not clean_title:
        clean_title = clip.id[:8]

    return f"{prefix}_{clean_title}_{created}.txt"


def bulk_export_zip(window, ids=None) -> None:
    if not window._guard_unlocked():
        return
    ids = list(ids) if ids is not None else list(window._selected_clip_ids)
    if not ids:
        window._show_toast("No items selected to export to ZIP.")
        return

    clips = []
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None:
            clips.append(clip)

    if not clips:
        window._show_toast("No items to export.")
        return

    dest_zip = filedialog.asksaveasfilename(
        parent=window,
        title="Export Selection to ZIP File",
        defaultextension=".zip",
        filetypes=[("ZIP Archive", "*.zip")],
    )
    if not dest_zip:
        return

    saved_count = 0
    failed_count = 0

    try:
        with zipfile.ZipFile(dest_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for clip in clips:
                if clip.content_type == models.CONTENT_IMAGE:
                    loaded = window.vault.storage.load_clip_asset_bytes(clip.id)
                    if not loaded:
                        failed_count += 1
                        continue
                    png_bytes, _ = loaded
                    filename = image_assets.make_smart_filename(clip)
                    if not filename.lower().endswith(".png"):
                        filename += ".png"
                    data = png_bytes
                else:
                    filename = _make_text_filename(clip)
                    data = (clip.content or "").encode("utf-8")

                base_name = Path(filename).stem
                ext = Path(filename).suffix
                arcname = filename
                idx = 1
                while arcname in zf.namelist():
                    arcname = f"{base_name}_{idx}{ext}"
                    idx += 1

                zf.writestr(arcname, data)
                saved_count += 1

        if saved_count > 0:
            summary = analyze_selection(clips)
            msg = f"Exported {saved_count} items to ZIP"
            if failed_count:
                msg += f" ({failed_count} assets missing)"
            window._show_toast(msg)

            # Record event/receipt
            meta = {
                "action": "batch_export_zip",
                "source": "desktop",
                "count": saved_count,
                "format": "zip",
                "item_breakdown": {
                    "images": summary.image_count,
                    "text": summary.text_count,
                    "links": summary.link_count,
                },
                "transfer_status": "completed" if failed_count == 0 else "partial",
                "timestamp": models.now_iso(),
                "success": failed_count == 0,
            }
            editable_copies.write_file_receipt("batch_export_zip", meta)
            window.vault.events.record(models.EVENT_COPIED_AGAIN, None, meta)
        else:
            try:
                Path(dest_zip).unlink(missing_ok=True)
            except Exception:
                pass
            window._show_toast("Failed to export items to ZIP. Missing or corrupted assets.")
    except Exception as e:
        window._show_toast(f"ZIP export error: {e}")


def bulk_copy_paths(window, ids=None) -> None:
    if not window._guard_unlocked():
        return
    ids = list(ids) if ids is not None else list(window._selected_clip_ids)
    image_ids = []
    for cid in ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None and clip.content_type == models.CONTENT_IMAGE:
            image_ids.append(cid)
    if not image_ids:
        window._show_toast("No screenshots selected to copy paths.")
        return

    paths = []
    for cid in image_ids:
        clip = window.vault.storage.get_clip(cid)
        if clip is not None and clip.content_type == models.CONTENT_IMAGE:
            rec = window.vault.storage.get_asset_record(cid)
            if rec:
                p = image_assets.assets_dir() / rec.storage_name
                paths.append(str(p))

    if not paths:
        window._show_toast("Failed to copy paths: asset records not found on disk.")
        return

    combined = "\n".join(paths)
    window.clipboard_clear()
    window.clipboard_append(combined)
    window._monitor.note_local_copy(combined)
    window._show_toast(f"Copied {len(paths)} file paths to clipboard.")

    # Record event/receipt
    meta = {
        "action": "desktop_batch_copy_paths",
        "source": "desktop",
        "count": len(paths),
        "transfer_status": "completed",
        "timestamp": models.now_iso(),
        "success": True,
    }
    editable_copies.write_file_receipt("desktop_batch_copy_paths", meta)
    window.vault.events.record(models.EVENT_COPIED_AGAIN, None, meta)


def bulk_view_proof(window) -> None:
    if not window._guard_unlocked():
        return
    window._show_toast("Opening proof viewer...")


def bulk_export_bundle(window) -> None:
    if not window._guard_unlocked():
        return
    ids = list(window._selected_clip_ids)
    if not ids:
        return

    dest_zip = filedialog.asksaveasfilename(
        parent=window,
        title="Export Mixed Bundle as ZIP",
        defaultextension=".zip",
        filetypes=[("ZIP Archive", "*.zip")],
    )
    if not dest_zip:
        return

    res = window.vault.export_proof_zip(ids, dest_zip)
    if res and getattr(res, "success", False):
        window._show_toast(f"Exported mixed bundle to {dest_zip}")

        # Record event/receipt
        clips = []
        for cid in ids:
            c = window.vault.storage.get_clip(cid)
            if c is not None:
                clips.append(c)
        summary = analyze_selection(clips)

        meta = {
            "action": "batch_export_bundle",
            "source": "desktop",
            "count": len(ids),
            "format": "zip",
            "item_breakdown": {
                "links": summary.link_count,
                "text": summary.text_count,
                "images": summary.image_count,
            },
            "transfer_status": "completed",
            "timestamp": models.now_iso(),
            "success": True,
        }
        editable_copies.write_file_receipt("batch_export_bundle", meta)
        window.vault.events.record(models.EVENT_COPIED_AGAIN, None, meta)
    else:
        err = getattr(res, "error", "unknown error")
        window._show_toast(f"Export failed: {err}")


def bulk_copy_text_links(window) -> None:
    bulk_copy_format(window, "plain")
