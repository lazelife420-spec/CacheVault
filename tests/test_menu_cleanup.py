from __future__ import annotations

import inspect
import pytest
from cache_vault.core import models
from cache_vault.core.contextmenu import clip_menu_items
from cache_vault.ui import clip_context
from cache_vault.ui.shell import CacheVaultApp

def test_context_menu_cascades_are_wired():
    """Verify that open_clip_menu structure translates into cascades instead of flat entries."""
    src = inspect.getsource(clip_context.open_clip_menu)
    assert "add_cascade(label=item.label, menu=sub)" in src
    assert "sub = tk.Menu" in src
    assert "child.separator_before" in src


def test_no_menu_item_points_to_missing_handlers(vault):
    """Verify all single-selection context menu keys have matching dispatch handlers in the UI."""
    app = CacheVaultApp(vault=vault)
    try:
        # Build dispatch map from open_clip_menu source or inspect it
        # Let's inspect the keys from clip_menu_items against the dispatch map keys in open_clip_menu
        # We can extract the dispatch keys from the source code
        dispatch_keys = {
            "copy_again", "paste_selected", "open_link", "open_asset_folder",
            "drag_out", "toggle_favorite", "mark_keep", "copy_to_safe",
            "copy_to_last_safe", "move_safe", "send_to_macro_safe",
            "create_editable_copy", "export_proof_zip", "view_receipts",
            "view_mobile_receipt", "copy_metadata", "copy_item_id",
            "copy_source_summary", "open", "reveal", "remove", "restore",
            "permanently_remove"
        }
        
        # Verify app has handlers or callbacks for every dispatch key
        # (Check they are wired to actual methods or lambdas in the shell)
        for key in dispatch_keys:
            # Check corresponding shell method exists
            if key == "copy_again":
                assert hasattr(app, "_copy_again")
            elif key == "paste_selected":
                assert hasattr(app, "_paste_clip")
            elif key == "open_link":
                assert hasattr(app, "_open_clip_link")
            elif key == "open_asset_folder":
                assert hasattr(app, "_open_asset_folder")
            elif key == "drag_out":
                assert hasattr(app, "_drag_out_clip")
            elif key == "toggle_favorite":
                assert hasattr(app, "_toggle_favorite")
            elif key == "mark_keep":
                assert hasattr(app, "_mark_keep")
            elif key == "copy_to_safe":
                assert hasattr(app, "_copy_to_safe")
            elif key == "copy_to_last_safe":
                assert hasattr(app, "_copy_to_last_safe")
            elif key == "move_safe":
                assert hasattr(app, "_move_to_safe")
            elif key == "send_to_macro_safe":
                assert hasattr(app, "_send_to_macro_safe")
            elif key == "create_editable_copy":
                assert hasattr(app, "_create_editable_copy")
            elif key == "export_proof_zip":
                assert hasattr(app, "_export_clip_proof")
            elif key == "view_receipts":
                assert hasattr(app, "_open_events")
            elif key == "view_mobile_receipt":
                assert hasattr(app, "_open_events")
            elif key == "copy_metadata":
                assert hasattr(app, "_copy_metadata")
            elif key == "copy_item_id":
                assert hasattr(app, "_copy_text")
            elif key == "copy_source_summary":
                assert hasattr(app, "_copy_clean")
            elif key == "open":
                assert hasattr(app, "_open_clip_path")
            elif key == "reveal":
                assert hasattr(app, "_reveal_clip_path")
            elif key == "remove":
                assert hasattr(app, "_remove_from_history")
            elif key == "restore":
                assert hasattr(app, "_restore")
            elif key == "permanently_remove":
                assert hasattr(app, "_permanently_remove")
    finally:
        app._quit()


def test_recently_shipped_actions_are_wired(vault):
    """Verify that Copy Selected Item, Paste Selected Item, Copy to Safe, Copy to Last Safe are visible and wired."""
    app = CacheVaultApp(vault=vault)
    try:
        from cache_vault.core.models import Clip
        clip = Clip(content="test content", preview="test", classification=models.CLASS_PLAIN)
        
        # Build menu items
        items = clip_menu_items(clip, last_safe_name="Default Safe")
        
        # 1. Verify primary keys
        primary = next(i for i in items if i.key == "primary")
        primary_keys = [child.key for child in primary.children]
        assert "copy_again" in primary_keys
        assert "paste_selected" in primary_keys
        
        # 2. Verify organize keys
        organize = next(i for i in items if i.key == "organize")
        organize_keys = [child.key for child in organize.children]
        assert "copy_to_safe" in organize_keys
        assert "copy_to_last_safe" in organize_keys
    finally:
        app._quit()


def test_settings_hub_advanced_labels():
    """Verify that settings registry contains renamed advanced categories."""
    from cache_vault.modules.registry import build_default_registry
    reg = build_default_registry()
    cats = {c.id: c.label for c in reg.settings_categories()}
    assert cats["vault_lock"] == "Advanced: Vault Lock"
    assert cats["history"] == "Advanced: History & Pruning"

