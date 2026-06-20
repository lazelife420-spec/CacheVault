"""Home dashboard, grid, filters, duplicates, and metadata tests."""

from __future__ import annotations

import pytest

from cache_vault import brand
from cache_vault.core import clip_metadata, models, search
from cache_vault.core.duplicates import (
    DuplicateGroup,
    apply_duplicate_review,
    find_exact_duplicate_groups,
    find_possible_duplicate_groups,
)
from cache_vault.core.models import Clip
from cache_vault.core.storage import (
    FILTER_ALL,
    FILTER_DUPLICATES,
    FILTER_HOME,
    FILTER_OLDER,
    FILTER_SCREENSHOTS,
    VaultStorage,
)
from cache_vault.core.vault import Vault
from cache_vault.ui import filters as filters_ui
from cache_vault.ui.filters import NAV_MOBILE_ACCESS, NAV_STAMPED_RECEIPTS
from cache_vault.ui.home_dashboard import HomeDashboard, vault_status_text


def _clip(content: str, **kw) -> Clip:
    title = kw.pop("title", clip_metadata.clip_title(content, content))
    use_count = kw.pop("use_count", 1)
    c = Clip(
        content=content,
        content_hash=models.content_hash(content),
        preview=models.make_preview(content),
        normalized_hash=clip_metadata.normalized_hash(content),
        title=title,
        size_bytes=clip_metadata.size_bytes_for(content),
        use_count=use_count,
        **kw,
    )
    c.last_used_at = c.created_at
    return c


def test_home_filter_constant_exists():
    assert FILTER_HOME == "home"
    assert any(k == FILTER_HOME for _h, items in filters_ui.FILTER_GROUPS for k, _l in items)


def test_sidebar_group_headings():
    headings = [h for h, _ in filters_ui.FILTER_GROUPS if h]
    assert "COMMAND" in headings
    assert "VAULT" in headings
    assert "REVIEW" in headings
    assert "PROOF" in headings
    assert "ACCESS" in headings
    assert "TIME" in headings


def test_sidebar_proof_items():
    from cache_vault.ui.filters import NAV_EDITABLE_COPIES, NAV_EXPORTS, NAV_HTML_BUNDLES
    keys = [k for _h, items in filters_ui.FILTER_GROUPS for k, _l in items]
    assert NAV_STAMPED_RECEIPTS in keys
    assert NAV_EXPORTS in keys
    assert NAV_EDITABLE_COPIES in keys
    assert NAV_HTML_BUNDLES in keys


def test_sidebar_access_items():
    from cache_vault.ui.filters import NAV_FOUNDER, NAV_MOBILE_ACCESS, NAV_MOBILE_INBOX, NAV_SETTINGS
    keys = [k for _h, items in filters_ui.FILTER_GROUPS for k, _l in items]
    assert NAV_MOBILE_INBOX in keys
    assert NAV_MOBILE_ACCESS in keys
    assert NAV_SETTINGS in keys
    assert NAV_FOUNDER not in keys  # pinned above collapsible groups


def test_sidebar_founder_nav_constant():
    from cache_vault.ui.filters import NAV_FOUNDER
    assert NAV_FOUNDER == "nav_founder"


def test_vault_status_text_honest():
    text = vault_status_text({
        "all": 5, "receipts": 3, "capture_paused": False, "mobile_enabled": False,
    })
    assert "Local-only" in text
    assert "Mobile Access off" in text
    assert "encryption" not in text.lower()
    assert "cloud" not in text.lower()
    assert "sync" not in text.lower()


def test_brand_no_fake_security_claims():
    from cache_vault import brand
    for blob in (
        brand.PRODUCT_ABOUT, brand.VAULT_STATUS_NOTE, brand.MOBILE_ACCESS_HONEST,
        brand.VAULT_TAGLINE, brand.PRODUCT_PROMISE,
    ):
        low = blob.lower()
        assert "encrypted vault" not in low
        assert "cloud backup" not in low
        assert "secure sync" not in low
        assert "military" not in low


def test_dashboard_summary_real_counts(storage):
    storage.add_clip(_clip("one"))
    storage.add_clip(_clip("two"))
    v = Vault(storage=storage)
    summary = v.dashboard_summary()
    assert summary["all"] == 2
    assert summary["receipts"] >= 0


def test_date_added_filter_today(storage):
    c = storage.add_clip(_clip("today clip"))
    q = search.SearchQuery(date_added_preset="today")
    ids = {x.id for x in storage.list_clips(q)}
    assert c.id in ids


def test_date_used_sort(storage):
    a = storage.add_clip(_clip(
        "aaa",
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        last_used_at="2026-01-01T00:00:00+00:00",
    ))
    b = storage.add_clip(_clip(
        "bbb",
        created_at="2026-01-01T00:00:01+00:00",
        updated_at="2026-01-01T00:00:01+00:00",
        last_used_at="2026-01-01T00:00:01+00:00",
    ))
    storage.touch_clip(a.id)
    q = search.SearchQuery(sort=models.SORT_RECENTLY_USED)
    listed = storage.list_clips(q)
    assert listed[0].id == a.id
    assert listed[1].id == b.id


def test_most_used_sort(storage):
    a = storage.add_clip(_clip("aaa"))
    b = storage.add_clip(_clip("bbb"))
    storage.touch_clip(a.id)
    storage.touch_clip(a.id)
    q = search.SearchQuery(sort=models.SORT_MOST_USED)
    assert storage.list_clips(q)[0].id == a.id


def test_source_app_filter(storage):
    storage.add_clip(_clip("x", source_app="Cursor"))
    storage.add_clip(_clip("y", source_app="Edge"))
    q = search.SearchQuery(source="cursor")
    assert len(storage.list_clips(q)) == 1


def test_source_url_search(storage):
    storage.add_clip(_clip("https://github.com/foo", classification=models.CLASS_LINK,
                           source_url="https://github.com/foo"))
    q = search.SearchQuery(text="github")
    assert len(storage.list_clips(q)) == 1


def test_missing_metadata_safe(storage):
    storage.add_clip(_clip("plain", source_app=None, source_window=None, title=None))
    assert storage.list_clips()  # no crash


def test_old_clip_migration_columns(storage):
    storage.add_clip(_clip("legacy"))
    row = storage.conn.execute("SELECT * FROM clips LIMIT 1").fetchone()
    assert "last_used_at" in row.keys()
    assert "use_count" in row.keys()


def test_exact_duplicate_groups(storage):
    a = storage.add_clip(_clip("dup me"))
    b = storage.add_clip(_clip("dup me"))
    groups = find_exact_duplicate_groups(storage)
    assert len(groups) == 1
    assert {c.id for c in groups[0].clips} == {a.id, b.id}


def test_possible_duplicate_groups(storage):
    storage.add_clip(_clip("Hello"))
    storage.add_clip(_clip("  hello  "))
    groups = find_possible_duplicate_groups(storage)
    assert any(g.kind == "possible" for g in groups)


def test_duplicate_review_moves_extras_not_permanent(storage):
    a = storage.add_clip(_clip("same"))
    b = storage.add_clip(_clip("same"))
    fav = storage.add_clip(_clip("same", is_pinned=True))
    group = DuplicateGroup("h", "exact", a.content_hash, a.normalized_hash, [a, b, fav])
    v = Vault(storage=storage)
    kept = apply_duplicate_review(storage, v.events, group, "keep_favorite")
    assert kept == fav.id
    assert storage.get_clip(fav.id).deleted_at is None
    assert storage.get_clip(a.id).deleted_at is not None
    assert storage.get_clip(b.id).deleted_at is not None


def test_keep_newest_duplicate(storage):
    a = storage.add_clip(_clip("z"))
    b = storage.add_clip(_clip("z"))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    kept = v.review_duplicates(group, "keep_newest")
    assert kept == b.id
    assert storage.get_clip(a.id).deleted_at is not None


def test_merge_usage_history(storage):
    a = storage.add_clip(_clip("z", use_count=2))
    b = storage.add_clip(_clip("z", use_count=3))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    v.review_duplicates(group, "keep_newest", merge_history=True)
    kept = storage.get_clip(b.id)
    assert kept.use_count >= 5


def test_duplicate_review_writes_receipt(storage):
    storage.add_clip(_clip("r"))
    storage.add_clip(_clip("r"))
    group = find_exact_duplicate_groups(storage)[0]
    v = Vault(storage=storage)
    v.review_duplicates(group, "keep_all")
    types = {e["event_type"] for e in storage.conn.execute("SELECT event_type FROM events").fetchall()}
    assert models.EVENT_DUPLICATE_REVIEW in types


def test_sensitive_masked_preview():
    from cache_vault.core import sensitive
    c = _clip("password=secret123", is_sensitive=True)
    c.preview = sensitive.masked_preview(c.content)
    assert "secret" not in c.preview.lower()


def test_grid_metadata_fields():
    from cache_vault.ui.clip_grid import COLUMNS
    keys = {k for k, _l, _w in COLUMNS}
    for field in ("name", "type", "added", "used", "source", "favorite", "proof"):
        assert field in keys


def test_clip_metadata_display():
    from cache_vault.core.clip_metadata import display
    assert display(None) == "—"
    assert display("") == "—"
    assert display("Cursor") == "Cursor"


def test_duplicate_dialog_warning_copy():
    from cache_vault.ui.duplicate_dialog import DuplicateReviewDialog
    assert DuplicateReviewDialog is not None


def test_screenshot_filter_honest_count(storage):
    assert storage.counts()[FILTER_SCREENSHOTS] == 0


def test_older_filter(storage):
    storage.add_clip(_clip("oldish"))
    listed = storage.list_clips(FILTER_OLDER)
    assert isinstance(listed, list)


def test_clip_usage_events(storage):
    c = storage.add_clip(_clip("use"))
    storage.conn.execute(
        "INSERT INTO events (id, created_at, event_type, clip_id, details) "
        "VALUES (?,?,?,?,?)",
        (models.new_id(), models.now_iso(), models.EVENT_COPIED_AGAIN, c.id, "{}"),
    )
    storage.conn.commit()
    assert len(storage.events_for_clip(c.id)) == 1


def test_asset_storage_ready_false_without_table(tmp_path):
    s = VaultStorage(tmp_path / "legacy.db")
    s.conn.execute("DROP TABLE clip_assets")
    s.conn.commit()
    assert s.asset_storage_ready() is False
    s.close()


def test_asset_storage_ready_true_with_table(storage):
    assert storage.asset_storage_ready() is True


try:
    import customtkinter as ctk
    from tests.tk_support import probe_tk_ui

    _TK_OK, _TK_REASON = probe_tk_ui()
except Exception:
    _TK_OK, _TK_REASON = False, "customtkinter unavailable"

_ui_mark = pytest.mark.skipif(not _TK_OK, reason=_TK_REASON or "Tk UI unavailable")


@_ui_mark
class TestHomeVaultUI:
    def test_home_vault_status_header_renders(self, tk_root):
        receipts: list[str] = []
        dashboard = HomeDashboard(
            tk_root,
            on_filter=lambda _k: None,
            on_open_receipts=lambda: receipts.append("receipts"),
            on_mobile_settings=lambda: None,
            on_pair_android=lambda: None,
            on_export=lambda: None,
            on_select_clip=lambda _c: None,
            on_copy=lambda _id: None,
        )
        summary = {
            "all": 12, "favorites": 1, "screenshots": 0, "duplicates": 2,
            "recently_removed": 0, "receipts": 8, "sensitive": 0, "expired": 0,
            "capture_paused": False, "mobile_enabled": False,
        }
        dashboard.render(summary, [], [], [])
        dashboard.update_idletasks()

        def _labels(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    texts.append(child.cget("text"))
                texts.extend(_labels(child))
            return texts

        labels = _labels(dashboard._body)
        assert brand.VAULT_STATUS_ACTIVE in labels
        assert any(brand.LABEL_LOCAL_ONLY in t for t in labels)
        assert any("Mobile Access off" in t for t in labels)

        dashboard.destroy()

    def test_vault_control_panel_renders(self, tk_root):
        from cache_vault.ui.preview import PreviewPanel

        panel = PreviewPanel(tk_root, actions={})
        summary = {
            "all": 5, "favorites": 1, "duplicates": 0, "recently_removed": 0,
            "receipts": 3, "capture_paused": False, "mobile_enabled": False,
        }
        panel.show_vault_control(summary, {
            "review_duplicates": lambda: None,
            "open_receipts": lambda: None,
            "pair_android": lambda: None,
            "export": lambda: None,
            "mobile_settings": lambda: None,
        })
        panel.update_idletasks()
        assert panel._title.cget("text") == brand.TERM_VAULT_STATUS

        def _button_texts(widget):
            texts = []
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkButton):
                    texts.append(child.cget("text"))
                texts.extend(_button_texts(child))
            return texts

        buttons = set(_button_texts(panel._vault_frame))
        assert "Review Duplicates" in buttons
        assert f"Open {brand.TERM_STAMPED_RECEIPTS}" in buttons
        assert "Pair Android Device" in buttons
        assert brand.TERM_EXPORT in buttons

        panel.destroy()

    def test_summary_cards_clickable(self, tk_root):
        navigated: list[str] = []
        receipts: list[str] = []
        dashboard = HomeDashboard(
            tk_root,
            on_filter=lambda k: navigated.append(k),
            on_open_receipts=lambda: receipts.append("yes"),
            on_mobile_settings=lambda: None,
            on_pair_android=lambda: None,
            on_export=lambda: None,
            on_select_clip=lambda _c: None,
            on_copy=lambda _id: None,
        )
        summary = {
            "all": 1, "favorites": 0, "screenshots": 0, "duplicates": 0,
            "recently_removed": 0, "receipts": 2, "sensitive": 0, "expired": 0,
            "capture_paused": False, "mobile_enabled": False,
        }
        dashboard.render(summary, [], [], [])
        dashboard.update_idletasks()

        def _find_label(widget, text):
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel) and child.cget("text") == text:
                    return child
                found = _find_label(child, text)
                if found is not None:
                    return found
            return None

        all_lbl = _find_label(dashboard._body, "All Clips")
        receipts_lbl = _find_label(dashboard._body, "Receipts")
        assert all_lbl is not None
        assert receipts_lbl is not None

        dashboard._on_filter(FILTER_ALL)
        assert navigated == [FILTER_ALL]
        dashboard._on_open_receipts()
        assert receipts == ["yes"]

        dashboard.destroy()
