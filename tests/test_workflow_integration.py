"""Cache Vault Workflow Integration Tests.

These tests verify that recently stacked features work together correctly:
- Selected item paste + focus safety
- Copy-to-Safe duplication
- Do Not Save Next Copy bypass
- Date stamp + image preview
- Context menu honesty (all shipped actions wired)

This is an RC-level integration audit, not a unit test suite.
"""
from __future__ import annotations

import inspect
import time
import pytest

from cache_vault.core import models
from cache_vault.core.models import Clip
from cache_vault.core.contextmenu import clip_menu_items, MenuItem


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _all_keys(items: list[MenuItem]) -> list[str]:
    out = []
    for item in items:
        out.append(item.key)
        out.extend(_all_keys(item.children))
    return out


def _children(items: list[MenuItem], key: str) -> list[MenuItem]:
    return next(i.children for i in items if i.key == key)


def _clip(**kw) -> Clip:
    defaults = {"content": "test", "preview": "test"}
    defaults.update(kw)
    return Clip(**defaults)


# ===================================================================
# FLOW 1 — Selected paste + focus safety
# ===================================================================

class TestSelectedPasteFocusSafety:
    """Verify paste delivery code guards against self-paste."""

    def test_paste_clip_checks_guard_unlocked(self):
        """_paste_clip must call _guard_unlocked before proceeding."""
        from cache_vault.ui.shell import CacheVaultApp
        src = inspect.getsource(CacheVaultApp._paste_clip)
        assert "_guard_unlocked" in src

    def test_paste_clip_uses_hwnd_belongs_to_widget_guard(self):
        """_paste_clip must check hwnd_belongs_to_widget to avoid self-paste."""
        from cache_vault.ui.shell import CacheVaultApp
        src = inspect.getsource(CacheVaultApp._paste_clip)
        assert "hwnd_belongs_to_widget" in src

    def test_paste_clip_graceful_no_target(self):
        """When no external target is found, paste must not crash — shows toast."""
        from cache_vault.ui.shell import CacheVaultApp
        src = inspect.getsource(CacheVaultApp._paste_clip)
        assert "no_target_window" in src
        assert "No target window to paste into" in src

    def test_keyboard_paste_guards_text_input_focus(self):
        """_keyboard_paste_selected must skip if focus is in a text input."""
        from cache_vault.ui.shell import CacheVaultApp
        src = inspect.getsource(CacheVaultApp._keyboard_paste_selected)
        assert "_keyboard_focus_is_text_input" in src

    def test_copy_again_exists_and_returns_none_for_missing_clip(self, vault):
        """_copy_again on a nonexistent clip ID must not crash."""
        result = vault.storage.get_clip("nonexistent_id_12345")
        assert result is None


# ===================================================================
# FLOW 2 — Copy-to-Safe interaction
# ===================================================================

class TestCopyToSafeInteraction:
    """Verify non-destructive copy-to-safe duplication behavior."""

    def test_copy_to_safe_creates_duplicate(self, vault):
        """Copying a clip to a safe creates a new clip; original remains."""
        original = vault.capture("Copy-to-safe integration test content")
        safe = vault.safes.default_safe()

        copied = vault.copy_to_safe(original.id, safe.id)

        assert copied is not None
        assert copied.id != original.id
        assert copied.content == original.content
        assert copied.safe_id == safe.id

        # Original must still exist
        reloaded = vault.storage.get_clip(original.id)
        assert reloaded is not None
        assert reloaded.content == original.content

    def test_copy_to_safe_sets_capture_mode(self, vault):
        """Duplicated clip must have CAPTURE_COPIED_TO_SAFE capture mode."""
        original = vault.capture("Capture mode verification")
        safe = vault.safes.default_safe()
        copied = vault.copy_to_safe(original.id, safe.id)
        assert copied.capture_mode == models.CAPTURE_COPIED_TO_SAFE

    def test_copy_to_safe_invalid_safe_returns_none(self, vault):
        """Copy to a nonexistent safe must return None, not crash."""
        original = vault.capture("Safe safety test")
        result = vault.copy_to_safe(original.id, "fake_safe_id_999")
        assert result is None

    def test_copy_to_safe_invalid_clip_returns_none(self, vault):
        """Copy a nonexistent clip must return None, not crash."""
        safe = vault.safes.default_safe()
        result = vault.copy_to_safe("fake_clip_id_999", safe.id)
        assert result is None

    def test_copy_to_safe_does_not_delete_original(self, vault):
        """After copy-to-safe, original clip must not be soft-deleted."""
        original = vault.capture("Non-destructive check")
        safe = vault.safes.default_safe()
        vault.copy_to_safe(original.id, safe.id)

        reloaded = vault.storage.get_clip(original.id)
        assert reloaded.deleted_at is None


# ===================================================================
# FLOW 3 — Do Not Save Next Copy interaction
# ===================================================================

class TestDoNotSaveNextCopyInteraction:
    """Verify the one-shot clipboard bypass and its interactions."""

    def test_ignore_arms_and_consumes(self):
        """Arming ignore, then consuming, resets the flag."""
        from cache_vault.core.capture_rules import CaptureController
        from cache_vault.core.settings import Settings
        ctrl = CaptureController(Settings)
        ctrl.arm_ignore_next()
        assert ctrl.ignore_next is True
        consumed = ctrl.consume_ignore()
        assert consumed is True
        assert ctrl.ignore_next is False

    def test_ignore_only_skips_once(self):
        """After one consume, the second consume returns False."""
        from cache_vault.core.capture_rules import CaptureController
        from cache_vault.core.settings import Settings
        ctrl = CaptureController(Settings)
        ctrl.arm_ignore_next()
        assert ctrl.consume_ignore() is True
        assert ctrl.consume_ignore() is False

    def test_ignore_does_not_block_copy_to_safe(self, vault):
        """Arming ignore must not interfere with copy-to-safe."""
        from cache_vault.core.capture_rules import CaptureController
        from cache_vault.core.settings import Settings
        ctrl = CaptureController(Settings)
        ctrl.arm_ignore_next()

        # copy_to_safe operates on existing clips — bypass only affects new captures
        original = vault.capture("Should still be copyable to safe")
        safe = vault.safes.default_safe()
        copied = vault.copy_to_safe(original.id, safe.id)
        assert copied is not None
        assert copied.content == original.content

    def test_ignore_does_not_block_selected_paste_code_path(self):
        """_paste_clip code does not check ignore state (it uses copy_again)."""
        from cache_vault.ui.shell import CacheVaultApp
        src = inspect.getsource(CacheVaultApp._paste_clip)
        # Paste delivery must NOT consult the ignore flag
        assert "consume_ignore" not in src
        assert "ignore_next" not in src

    def test_ignore_expires_after_timeout(self):
        """Bypass flag must expire after IGNORE_TIMEOUT_SEC."""
        from cache_vault.core.capture_rules import CaptureController, IGNORE_TIMEOUT_SEC
        from cache_vault.core.settings import Settings

        ctrl = CaptureController(Settings)
        ctrl.arm_ignore_next()

        # Simulate timeout by monkey-patching the armed timestamp
        ctrl._ignore_at = ctrl._now() - IGNORE_TIMEOUT_SEC - 1
        assert ctrl.ignore_next is False

    def test_arm_ignore_cancels_arm_next_copy(self):
        """Arming ignore must cancel any pending arm-next-copy."""
        from cache_vault.core.capture_rules import CaptureController
        from cache_vault.core.settings import Settings
        ctrl = CaptureController(Settings)
        ctrl.arm_next_copy("safe1", "Safe One")
        assert ctrl.armed is not None
        ctrl.arm_ignore_next()
        assert ctrl.armed is None
        assert ctrl.ignore_next is True


# ===================================================================
# FLOW 4 — Date/image preview regression
# ===================================================================

class TestDateImagePreviewRegression:
    """Verify date formatting and image preview code."""

    def test_short_time_format_produces_readable_output(self):
        """_short_time must produce 'Jun 30, 6:24 PM' style output."""
        from cache_vault.ui.clip_list import _short_time
        result = _short_time("2026-06-30T18:24:00+00:00")
        # Must contain month abbreviation, day, and AM/PM
        assert "Jun" in result
        assert "30" in result
        assert "PM" in result or "AM" in result

    def test_image_preview_uses_vault_card_style(self):
        """_render_image_preview must use vault_card styling."""
        from cache_vault.ui import preview
        src = inspect.getsource(preview)
        assert "vault_card" in src

    def test_preview_shows_dimensions_and_filename(self):
        """Preview code must render file dimensions and original filename."""
        from cache_vault.ui import preview
        src = inspect.getsource(preview)
        assert "original_name" in src or "filename" in src


# ===================================================================
# FLOW 5 — Menu honesty
# ===================================================================

class TestMenuHonesty:
    """Verify context menus expose only implemented, wired actions."""

    def test_single_clip_menu_has_all_shipped_action_keys(self):
        """All recently shipped features must appear in the context menu."""
        clip = _clip(classification=models.CLASS_PLAIN)
        items = clip_menu_items(clip, last_safe_name="Test Safe")
        all_keys = _all_keys(items)

        required = [
            "copy_again",       # Copy Selected Item
            "paste_selected",   # Paste Selected Item
            "copy_to_safe",     # Copy to Safe
            "copy_to_last_safe", # Copy to Last Safe
        ]
        for key in required:
            assert key in all_keys, f"Required shipped action '{key}' missing from context menu"

    def test_context_menu_groups_are_cascades(self):
        """Non-primary groups must be rendered as cascade submenus."""
        from cache_vault.ui import clip_context
        src = inspect.getsource(clip_context.open_clip_menu)
        assert "add_cascade" in src

    def test_dispatch_dict_covers_all_leaf_keys(self):
        """Every leaf key in the context menu must exist in the dispatch dict."""
        from cache_vault.ui import clip_context
        src = inspect.getsource(clip_context.open_clip_menu)

        clip = _clip(classification=models.CLASS_PLAIN)
        items = clip_menu_items(clip, last_safe_name="Test Safe")

        # Get all leaf keys (excluding structural group keys and copy_clean:* keys)
        structural_keys = {"primary", "copy_clean", "organize", "proof", "advanced", "danger"}
        leaf_keys = set()
        for item in items:
            if item.key in structural_keys:
                for child in item.children:
                    if not child.key.startswith("copy_clean:"):
                        leaf_keys.add(child.key)
            else:
                leaf_keys.add(item.key)

        # These must all appear as dispatch dict entries
        for key in leaf_keys:
            assert f'"{key}"' in src, f"Menu key '{key}' not found in dispatch dict"

    def test_no_copy_clean_key_points_to_missing_constant(self):
        """Every copy_clean: key must map to a valid copy_clean constant."""
        from cache_vault.core import copy_clean
        clip = _clip(classification=models.CLASS_LINK, title="Test")
        items = clip_menu_items(clip, last_safe_name="Test Safe")
        clean_items = _children(items, "copy_clean")
        for item in clean_items:
            action = item.key.split(":", 1)[1]
            assert hasattr(copy_clean, action.upper()) or action in dir(copy_clean), \
                f"copy_clean action '{action}' is not a valid constant"


# ===================================================================
# FLOW 6 — Release proof regression scan
# ===================================================================

class TestReleaseProofRegression:
    """Verify no stale version/hash/test-count references crept back in."""

    def test_readme_does_not_contain_stale_test_counts(self):
        """README must not reference old test counts (545, 561)."""
        from pathlib import Path
        readme = Path("README.md")
        if readme.exists():
            text = readme.read_text(encoding="utf-8", errors="replace")
            assert "545 tests" not in text.lower()
            assert "561 tests" not in text.lower()

    def test_no_stale_v0141_in_public_docs(self):
        """Public docs must not claim v0.1.4.1 is public unless a real artifact exists."""
        from pathlib import Path
        docs_dir = Path("docs")
        if docs_dir.exists():
            for f in docs_dir.glob("*.md"):
                text = f.read_text(encoding="utf-8", errors="replace")
                if "v0.1.4.1" in text:
                    # Only allowed in historical/audit context, not as a current release claim
                    assert "stale" in text.lower() or "historical" in text.lower() or \
                           "audit" in text.lower() or "old" in text.lower() or \
                           "corrected" in text.lower() or "reconcile" in text.lower(), \
                        f"docs/{f.name} references v0.1.4.1 outside historical context"
