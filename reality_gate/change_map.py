"""Deterministic change-map for Reality Gate.

This is the checked-in mapping from changed source files to required test
lanes, plus the escalation rules. It is deliberately data expressed in Python
(zero extra dependencies, fully commented, reviewable) so that tier routing is
deterministic — not AI guessing.

Escalation ladder: fast -> engineering -> product -> canonical.

Rules (applied per changed path, repo-relative, forward slashes):
  * packaging-sensitive input  -> force CANONICAL
        (the PyInstaller build / packaged runtime smoke must run)
  * gate/build tooling          -> force CANONICAL
        (scripts/ tools/ .github/ define the authoritative gate itself)
  * orchestrator (reality_gate/) -> force PRODUCT
        (routing change: run the broad suite, not the canonical packaging gate)
  * shared test infra           -> force PRODUCT
        (conftest/sandbox/tk_support affect every test)
  * mapped cache_vault/** source -> run its lanes (no escalation)
  * unmapped cache_vault/** source -> force PRODUCT (broad/full suite)
        conservative: central/shared modules (vault.py, models.py, settings.py,
        events.py, capabilities.py, shell.py, ...) are intentionally unmapped
        so they escalate rather than silently run a narrow lane
  * tests/** (a test file)      -> run that test file (no escalation)
  * other (docs, non-bundled assets) -> fast tripwires only

The selected tier is a FLOOR: escalation only raises the effective tier.
"""
from __future__ import annotations

import fnmatch
from dataclasses import dataclass

from .pipelines import TIER_RANK, max_tier

# ---------------------------------------------------------------------------
# Lanes: groups of test files that exercise one functional area.
# ---------------------------------------------------------------------------

LANE_CLIPBOARD = (
    "tests/test_clipboard_refresh.py",
    "tests/test_clipboard_open_retry.py",
    "tests/test_clipboard_self_capture.py",
    "tests/test_clipboard_text_fidelity.py",
    "tests/test_clipboard_image_fingerprint.py",
)
LANE_CUSTODY = (
    "tests/test_clipboard_custody.py",
    "tests/test_clipboard_custody_race.py",
    "tests/test_clipboard_custody_retry.py",
)
LANE_STORAGE = (
    "tests/test_storage.py",
    "tests/test_storage_health.py",
    "tests/test_storage_pagination.py",
    "tests/test_migration.py",
)
LANE_EXPORT = (
    "tests/test_export.py",
    "tests/test_drag_export.py",
    "tests/test_html_bundles.py",
    "tests/test_proof_exports.py",
    "tests/test_editable_copies.py",
)
LANE_RECEIPTS = (
    "tests/test_app_receipt.py",
    "tests/test_receipt_ledger.py",
    "tests/test_proof_exports.py",
    "tests/test_proof_manifest_completeness.py",
)
LANE_FOUNDER = (
    "tests/test_licensing.py",
    "tests/test_feature_gate.py",
    "tests/test_app_receipt.py",
    "tests/test_proof_exports.py",
)
LANE_QUICKPASTE = (
    "tests/test_quick_paste.py",
    "tests/test_paste_delivery.py",
    "tests/test_quick_paste_clipboard_restore.py",
)
LANE_COMMAND_CENTER = (
    "tests/test_command_center.py",
    "tests/test_command_center_ui.py",
    "tests/test_command_center_app.py",
)
LANE_CLEANUP = (
    "tests/test_cleanup_actions.py",
    "tests/test_cleanup_store.py",
    "tests/test_cleanup_suggestions.py",
    "tests/test_cleanup_scan_integration.py",
    "tests/test_cleanup_screen.py",
    "tests/test_cleanup_suppression.py",
)
LANE_VAULTLOCK = (
    "tests/test_vault_lock.py",
    "tests/test_vault_lock_ui.py",
)
LANE_MACRO = (
    "tests/test_macro_execute.py",
    "tests/test_macro_dialogs.py",
    "tests/test_vault_macros.py",
    "tests/test_regex_macros.py",
    "tests/test_macro_shortcut_listener.py",
)
LANE_MOBILE = (
    "tests/test_mobile_bridge.py",
    "tests/test_mobile_pairing.py",
    "tests/test_mobile_inbox.py",
    "tests/test_mobile_image_inbox.py",
    "tests/test_mobile_discovery.py",
    "tests/test_mobile_connection_lifecycle.py",
    "tests/test_mobile_access_screen.py",
    "tests/test_mobile_send_ignores_capture_pause.py",
    "tests/test_connection_doctor.py",
    "tests/test_f2_extension_inbox.py",
    "tests/test_f2_5_extension_security_gate.py",
    "tests/test_d3_mobile_model.py",
    "tests/test_d3_5_compatibility.py",
)
LANE_SEARCH = (
    "tests/test_search.py",
    "tests/test_search_universal.py",
    "tests/test_search_discoverability.py",
    "tests/test_search_during_batch_render.py",
)
LANE_SENSITIVE = ("tests/test_sensitive.py",)
LANE_SMART = ("tests/test_smart_folders.py", "tests/test_smart_save_name.py")
LANE_DELETE = (
    "tests/test_permanent_delete.py",
    "tests/test_permanent_delete_ui.py",
    "tests/test_recently_removed.py",
)
LANE_HOTKEY = ("tests/test_hotkey.py", "tests/test_hotkey_status.py")
LANE_CLASSIFY = ("tests/test_classify.py",)
LANE_SAFEIO = ("tests/test_safe_io.py", "tests/test_pathutil.py")
LANE_LANIP = ("tests/test_lan_ip_resolver.py", "tests/test_lan_ip_selection.py")
LANE_CAPTURE_RULES = ("tests/test_capture_rules.py",)
LANE_MULTI_LINK = ("tests/test_multi_link.py",)
LANE_COLLECTIONS = ("tests/test_collections.py", "tests/test_collections_ux.py")
LANE_IMAGE = ("tests/test_image_assets.py", "tests/test_image_clipboard.py")
LANE_COPY_CLEAN = (
    "tests/test_copy_clean.py",
    "tests/test_copy_combined_native_custody.py",
)
LANE_EDITABLE = (
    "tests/test_editable_copies.py",
    "tests/test_edit_clip_text_lifecycle.py",
)
LANE_DRAG = ("tests/test_drag_export.py",)
LANE_SELECTION = (
    "tests/test_clip_selection.py",
    "tests/test_selection_scope.py",
    "tests/test_selection_repaint_minimal.py",
)
LANE_CLIP_RENDER = (
    "tests/test_clip_render_cap.py",
    "tests/test_clip_labels_grouping.py",
    "tests/test_large_vault_render_batching.py",
)
LANE_CLIP_RECOVERY = ("tests/test_clip_recovery.py",)
LANE_CLEAR_ALL = ("tests/test_clear_all_clips.py",)
LANE_CONTEXTMENU = (
    "tests/test_contextmenu.py",
    "tests/test_clip_context_menu.py",
    "tests/test_menu_context.py",
    "tests/test_menu_lifecycle.py",
)
LANE_DIALOGS = (
    "tests/test_dialogs.py",
    "tests/test_dialog_placement.py",
    "tests/test_dialog_bring_to_front_teardown_race.py",
    "tests/test_destructive_confirmations.py",
    "tests/test_combine_dialog_lifecycle.py",
)
LANE_FIRST_USE = (
    "tests/test_first_use_guide.py",
    "tests/test_first_use_guide_titlebar_teardown.py",
)
LANE_HOME = ("tests/test_home_dashboard.py",)
LANE_PHOTO = ("tests/test_photo_viewer.py",)
LANE_PREVIEW = (
    "tests/test_preview_panel_narrow_width.py",
    "tests/test_view_panel_retention.py",
)
LANE_RECEIPT_LEDGER = ("tests/test_receipt_ledger.py",)
LANE_SCROLL = (
    "tests/test_scroll_patch.py",
    "tests/test_scroll_patch_api_compat.py",
    "tests/test_win_scroll.py",
)
LANE_SETTINGS = (
    "tests/test_settings_hub.py",
    "tests/test_settings_hub_integration.py",
)
LANE_SIDEBAR = (
    "tests/test_sidebar_context.py",
    "tests/test_sidebar_menu_context.py",
)
LANE_TEXTBOX = ("tests/test_ctk_textbox_scrollbar_teardown.py",)
LANE_THEME = ("tests/test_theme.py",)
LANE_TOAST = ("tests/test_toast_destroy_teardown.py",)
LANE_TOOLTIP = ("tests/test_tooltip.py",)
LANE_TRAY = ("tests/test_tray.py",)
LANE_VAULT_SCREENS = (
    "tests/test_all_clips_polish.py",
    "tests/test_view_panel_retention.py",
    "tests/test_clip_render_cap.py",
)
LANE_FONT = ("tests/test_font_finalizer_guard.py",)
LANE_CLI = ("tests/test_cli.py",)
LANE_BUILD_META = ("tests/test_build_meta.py",)
LANE_NAV = (
    "tests/test_navigation.py",
    "tests/test_startup.py",
    "tests/test_single_instance.py",
    "tests/test_module_registry.py",
    "tests/test_module_launchers.py",
)
LANE_FILTERS = ("tests/test_filter_nav_sidebar_menu.py",)
LANE_BATCH = ("tests/test_bulk_vault_actions.py",)

# ---------------------------------------------------------------------------
# Source file -> lane(s). Directory-prefix keys end with "/".
#
# Intentionally UNMAPPED (-> escalate to product / broad):
#   cache_vault/core/vault.py        (central module)
#   cache_vault/core/models.py       (shared data models)
#   cache_vault/core/settings.py     (shared config model)
#   cache_vault/core/events.py       (shared event bus)
#   cache_vault/core/capabilities.py (shared capability map)
#   cache_vault/core/capture_debug.py, win_mouse.py
#   cache_vault/ui/shell.py          (268KB central UI shell)
#   cache_vault/ui/page_header.py, page_scaffold.py, crashlog.py, icon.py
#   cache_vault/__init__.py, cache_vault/core/__init__.py, cache_vault/ui/__init__.py
# Add explicit entries here when a central module grows a dedicated test lane.
# ---------------------------------------------------------------------------

CHANGE_MAP: dict[str, tuple[str, ...]] = {
    # capture / clipboard spine
    "cache_vault/core/clipboard.py": LANE_CLIPBOARD,
    "cache_vault/core/clipboard_custody.py": LANE_CUSTODY,
    "cache_vault/core/clipboard_out.py": LANE_CLIPBOARD + LANE_QUICKPASTE,
    "cache_vault/core/capture_rules.py": LANE_CAPTURE_RULES,
    "cache_vault/core/capture_receipts.py": LANE_RECEIPTS,
    # classify / sensitive / smart
    "cache_vault/core/classify.py": LANE_CLASSIFY,
    "cache_vault/core/sensitive.py": LANE_SENSITIVE,
    "cache_vault/core/smart_folders.py": LANE_SMART,
    # cleanup
    "cache_vault/core/cleanup_actions.py": LANE_CLEANUP,
    "cache_vault/core/cleanup_store.py": LANE_CLEANUP,
    "cache_vault/core/cleanup_suggestions.py": LANE_CLEANUP,
    "cache_vault/core/cleanup_receipts.py": LANE_CLEANUP,
    "cache_vault/core/clear_all_receipts.py": LANE_CLEAR_ALL,
    # clips
    "cache_vault/core/clip_accents.py": LANE_CLIP_RENDER,
    "cache_vault/core/clip_metadata.py": LANE_CLIP_RENDER,
    "cache_vault/core/clip_recovery.py": LANE_CLIP_RECOVERY,
    "cache_vault/core/clip_recovery_import.py": LANE_CLIP_RECOVERY,
    "cache_vault/core/collection_receipts.py": LANE_COLLECTIONS,
    # command center
    "cache_vault/core/command_center.py": LANE_COMMAND_CENTER,
    # context menu / copy / drag
    "cache_vault/core/contextmenu.py": LANE_CONTEXTMENU,
    "cache_vault/core/copy_clean.py": LANE_COPY_CLEAN,
    "cache_vault/core/drag_export.py": LANE_DRAG,
    "cache_vault/core/duplicates.py": LANE_CLIPBOARD,
    "cache_vault/core/editable_copies.py": LANE_EDITABLE,
    # export / proof pack
    "cache_vault/core/export.py": LANE_EXPORT,
    "cache_vault/core/exports.py": LANE_EXPORT,
    "cache_vault/core/formatter.py": LANE_CLIPBOARD,
    "cache_vault/core/grouping.py": LANE_CLIP_RENDER,
    # hotkey
    "cache_vault/core/hotkey.py": LANE_HOTKEY,
    # images
    "cache_vault/core/image_assets.py": LANE_IMAGE,
    # lan ip
    "cache_vault/core/lan_ip.py": LANE_LANIP,
    # macros
    "cache_vault/core/macro_execute.py": LANE_MACRO,
    "cache_vault/core/macro_receipts.py": LANE_RECEIPTS,
    "cache_vault/core/macro_shortcut_listener.py": LANE_MACRO,
    "cache_vault/core/macro_variables.py": LANE_MACRO,
    "cache_vault/core/regex_macros.py": LANE_MACRO,
    # menu / multi-link / paste / paths
    "cache_vault/core/menu_context.py": LANE_CONTEXTMENU,
    "cache_vault/core/multi_link.py": LANE_MULTI_LINK,
    "cache_vault/core/paste_delivery.py": LANE_QUICKPASTE,
    "cache_vault/core/pathutil.py": LANE_SAFEIO,
    "cache_vault/core/permanent_delete.py": LANE_DELETE,
    # safes / io
    "cache_vault/core/safes.py": LANE_STORAGE,
    "cache_vault/core/safe_io.py": LANE_SAFEIO,
    # search / selection / sidebar
    "cache_vault/core/search.py": LANE_SEARCH,
    "cache_vault/core/selection.py": LANE_SELECTION,
    "cache_vault/core/sidebar_menu_context.py": LANE_SIDEBAR,
    "cache_vault/core/single_instance.py": LANE_NAV,
    "cache_vault/core/startup.py": LANE_NAV,
    # storage
    "cache_vault/core/storage.py": LANE_STORAGE,
    "cache_vault/core/storage_health.py": LANE_STORAGE,
    # vault lock / macros
    "cache_vault/core/vault_lock.py": LANE_VAULTLOCK,
    "cache_vault/core/vault_macros.py": LANE_MACRO,
    # mobile bridge (directory prefix -> whole mobile lane)
    "cache_vault/core/mobile/": LANE_MOBILE,

    # ---- UI ----
    "cache_vault/ui/batch_actions.py": LANE_BATCH,
    "cache_vault/ui/cleanup_screen.py": LANE_CLEANUP,
    "cache_vault/ui/clipboard_write.py": LANE_CLIPBOARD,
    "cache_vault/ui/clip_context.py": LANE_CONTEXTMENU,
    "cache_vault/ui/clip_grid.py": LANE_CLIP_RENDER,
    "cache_vault/ui/clip_list.py": LANE_CLIP_RENDER,
    "cache_vault/ui/clip_workflows.py": LANE_SELECTION,
    "cache_vault/ui/command_center.py": LANE_COMMAND_CENTER,
    "cache_vault/ui/dialogs.py": LANE_DIALOGS,
    "cache_vault/ui/duplicate_dialog.py": LANE_DIALOGS,
    "cache_vault/ui/filters.py": LANE_FILTERS,
    "cache_vault/ui/first_use_guide.py": LANE_FIRST_USE,
    "cache_vault/ui/font_patch.py": LANE_FONT,
    "cache_vault/ui/founder.py": LANE_FOUNDER,
    "cache_vault/ui/guide_copy.py": LANE_FIRST_USE,
    "cache_vault/ui/home_dashboard.py": LANE_HOME,
    "cache_vault/ui/hotkey_recording.py": LANE_HOTKEY,
    "cache_vault/ui/macro_dialogs.py": LANE_MACRO,
    "cache_vault/ui/macro_picker.py": LANE_MACRO,
    "cache_vault/ui/mobile_dialogs.py": LANE_MOBILE,
    "cache_vault/ui/pairing_help.py": LANE_MOBILE,
    "cache_vault/ui/photo_viewer.py": LANE_PHOTO,
    "cache_vault/ui/preview.py": LANE_PREVIEW,
    "cache_vault/ui/quick_paste.py": LANE_QUICKPASTE,
    "cache_vault/ui/receipt_ledger.py": LANE_RECEIPT_LEDGER,
    "cache_vault/ui/regex_macro_dialog.py": LANE_MACRO,
    "cache_vault/ui/scroll_patch.py": LANE_SCROLL,
    "cache_vault/ui/settings_hub.py": LANE_SETTINGS,
    "cache_vault/ui/sidebar_actions.py": LANE_SIDEBAR,
    "cache_vault/ui/sidebar_context.py": LANE_SIDEBAR,
    "cache_vault/ui/textbox.py": LANE_TEXTBOX,
    "cache_vault/ui/theme.py": LANE_THEME,
    "cache_vault/ui/themes/": LANE_THEME,
    "cache_vault/ui/toast.py": LANE_TOAST,
    "cache_vault/ui/tooltip.py": LANE_TOOLTIP,
    "cache_vault/ui/tray.py": LANE_TRAY,
    "cache_vault/ui/vault_lock.py": LANE_VAULTLOCK,
    "cache_vault/ui/vault_screens.py": LANE_VAULT_SCREENS,
    "cache_vault/ui/win_scroll.py": LANE_SCROLL,

    # ---- top-level package ----
    "cache_vault/cli.py": LANE_CLI,
    "cache_vault/feature_gate.py": LANE_FOUNDER,
    "cache_vault/licensing.py": LANE_FOUNDER,
    "cache_vault/brand.py": LANE_IMAGE,
    # cache_vault/build_meta.py is packaging-sensitive (see PACKAGING_SENSITIVE).
}

# ---------------------------------------------------------------------------
# Escalation pattern groups.
# ---------------------------------------------------------------------------

# Changes that MUST run the canonical gate (packaging + packaged runtime).
PACKAGING_SENSITIVE = (
    "packaging/**",
    "packaging/cache_vault.spec",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "app.py",
    "cache_vault/build_meta.py",
    "assets/cache-vault-icon.ico",
    "assets/cache-vault-icon-256.png",
    "cache_vault/ui/themes/proof_foundry.json",
)

# Changes to the authoritative gate / build-verification tooling -> canonical.
GATE_TOOLING_CANONICAL = (
    "scripts/**",
    "tools/**",
    ".github/**",
)

# Orchestrator changes -> broad product suite (routing, not coverage semantics).
GATE_TOOLING_PRODUCT = (
    "reality_gate/**",
)

# Shared test infrastructure -> broad product suite.
TEST_INFRA = frozenset(
    {
        "tests/conftest.py",
        "tests/sandbox.py",
        "tests/tk_support.py",
    }
)


@dataclass
class Resolution:
    """Result of mapping a diff onto lanes + escalation."""

    lanes: list[str]
    forced_tier: str | None
    reasons: list[str]
    changed_paths: list[str]


def _norm(p: str) -> str:
    return p.replace("\\", "/")


def _matches(p: str, patterns) -> bool:
    for pat in patterns:
        if pat.endswith("/**"):
            prefix = pat[:-2]  # "scripts/"
            if p.startswith(prefix):
                return True
        elif pat.endswith("/"):
            if p.startswith(pat):
                return True
        elif "*" in pat or "?" in pat:
            if fnmatch.fnmatch(p, pat):
                return True
        else:
            if p == pat:
                return True
    return False


def _lookup(p: str) -> tuple[str, ...] | None:
    """Return lanes for a cache_vault path, or None if unmapped."""
    if p in CHANGE_MAP:
        return CHANGE_MAP[p]
    for key, lane in CHANGE_MAP.items():
        if key.endswith("/") and p.startswith(key):
            return lane
    return None


def resolve_diff(changed_paths: list[str]) -> Resolution:
    """Map changed paths to lanes + a forced tier (conservative escalation)."""
    lanes: set[str] = set()
    forced: str | None = None
    reasons: list[str] = []

    for raw in changed_paths:
        p = _norm(raw)
        if not p:
            continue
        if _matches(p, PACKAGING_SENSITIVE):
            reasons.append(f"{p}: packaging-sensitive -> canonical")
            forced = max_tier(forced, "canonical")
        elif _matches(p, GATE_TOOLING_CANONICAL):
            reasons.append(f"{p}: gate/build tooling -> canonical")
            forced = max_tier(forced, "canonical")
        elif _matches(p, GATE_TOOLING_PRODUCT):
            reasons.append(f"{p}: orchestrator change -> product (broad)")
            forced = max_tier(forced, "product")
        elif p in TEST_INFRA:
            reasons.append(f"{p}: shared test infra -> product (broad)")
            forced = max_tier(forced, "product")
        elif p.startswith("tests/"):
            if p.endswith(".py"):
                lanes.add(p)
            else:
                reasons.append(f"{p}: non-test file under tests/ -> fast only")
        elif p.startswith("cache_vault/"):
            mapped = _lookup(p)
            if mapped is None:
                reasons.append(f"{p}: unmapped app source -> product (broad)")
                forced = max_tier(forced, "product")
            elif mapped:
                lanes.update(mapped)
            else:
                reasons.append(f"{p}: mapped (no dedicated lane)")
        else:
            reasons.append(f"{p}: non-source -> fast tripwires only")

    return Resolution(
        lanes=sorted(lanes),
        forced_tier=forced,
        reasons=reasons,
        changed_paths=[_norm(c) for c in changed_paths if c],
    )


def tier_index(t: str) -> int:
    return TIER_RANK[t]
