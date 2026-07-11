import pytest
import tkinter as tk
import customtkinter as ctk
from unittest.mock import MagicMock, patch

from cache_vault.core import storage as S
from cache_vault.core.settings import Settings
from cache_vault.ui.filters import (
    FilterNav, SidebarRow, SidebarSectionHeader,
    NAV_FOUNDER, NAV_QUICK_PASTE, NAV_VAULT_MACROS
)
from cache_vault.ui import sidebar_context
from cache_vault.ui import clip_context

class FakeWindow(ctk.CTkFrame):
    def __init__(self, master, settings):
        super().__init__(master)
        self.settings = settings
        self.vault = MagicMock()
        self.vault.settings = settings
        self._on_select_calls = []
        self._nav_calls = []

        # Stub methods needed by context menus
        self._schedule_quick_paste = MagicMock()
        self._open_settings = MagicMock()
        self._navigate_screen = MagicMock()
        self._open_new_safe = MagicMock()
        self._rename_safe = MagicMock()
        self._customize_safe_text = MagicMock()
        self._copy_safe_summary = MagicMock()
        self._set_default_safe = MagicMock()
        self._open_founder = MagicMock()

        # Instantiate FilterNav
        self._filters = FilterNav(
            self,
            on_select=self._on_select,
            settings=settings,
            on_safe_context=self._on_safe_context,
            on_collection_context=self._on_collection_context,
            on_section_context=self._on_section_context,
            on_nav_context=self._on_nav_context
        )
        self._filters.pack(fill="both", expand=True)

    def _on_select(self, key):
        self._on_select_calls.append(key)

    def _locked(self):
        return False

    def _on_safe_context(self, safe, x, y):
        sidebar_context.open_safe_menu(self, safe, x, y)

    def _on_collection_context(self, name, x, y):
        clip_context.open_collection_sidebar_menu(self, name, x, y)

    def _on_section_context(self, heading, x, y):
        if heading == "SAFES":
            sidebar_context.open_safes_heading_menu(self, x, y)
        else:
            sidebar_context.open_section_heading_menu(self, heading, x, y)

    def _on_nav_context(self, nav_key, x, y):
        sidebar_context.open_nav_row_menu(self, nav_key, x, y)

    def _navigate_filter(self, key):
        self._nav_calls.append(key)


def get_menu_items(menu: tk.Menu) -> list[dict]:
    items = []
    size = menu.index("end")
    if size is None:
        return items
    for i in range(size + 1):
        try:
            itype = menu.type(i)
            if itype == "separator":
                items.append({"type": "separator"})
            elif itype == "command":
                items.append({
                    "type": "command",
                    "label": menu.entrycget(i, "label"),
                    "state": menu.entrycget(i, "state")
                })
        except Exception:
            pass
    return items


def test_sidebar_context_menus(tk_root, tmp_path):
    settings = Settings()
    window = FakeWindow(tk_root, settings)
    window.pack(fill="both", expand=True)

    captured_menus = []

    def dummy_popup(menu, x, y):
        captured_menus.append(menu)

    with patch("tkinter.Menu.tk_popup", dummy_popup), \
         patch("cache_vault.ui.clip_context.destroy_menu", MagicMock()):

        # 1. Built-in navigation row context menu (e.g. Quick Paste)
        row = window._filters._rows[NAV_QUICK_PASTE]
        row._on_right_click(MagicMock(x_root=100, y_root=100))

        assert len(captured_menus) == 1
        menu = captured_menus.pop()
        items = get_menu_items(menu)
        labels = [item.get("label") for item in items if item.get("label")]
        assert "Open" in labels
        assert "Configure Hotkey" in labels

        # 2. Section Header context menu (e.g. VAULT)
        header = window._filters._section_headers["VAULT"]
        header._on_right_click(MagicMock(x_root=100, y_root=100))

        assert len(captured_menus) == 1
        menu = captured_menus.pop()
        items = get_menu_items(menu)
        labels = [item.get("label") for item in items if item.get("label")]
        assert "Expand Section" in labels
        assert "Collapse Section" in labels

        # 3. User-created Safe context menu vs Built-in Safe context menu
        window._filters.update_safes([
            {"id": "builtin_safe", "name": "Builtin Safe", "builtin": True, "count": 1},
            {"id": "user_safe", "name": "User Safe", "builtin": False, "count": 1}
        ])

        # Pre-select built-in safe to establish a selection
        row_builtin = window._filters._safe_rows[S.SAFE_PREFIX + "builtin_safe"]
        row_builtin._select_clicked()
        assert window._on_select_calls[-1] == S.SAFE_PREFIX + "builtin_safe"

        # Right click on user safe (clicked row becomes context target)
        row_user = window._filters._safe_rows[S.SAFE_PREFIX + "user_safe"]
        row_user._on_right_click(MagicMock(x_root=100, y_root=100))

        # Check selection was updated before the context menu action
        assert window._on_select_calls[-1] == S.SAFE_PREFIX + "user_safe"

        assert len(captured_menus) == 1
        menu = captured_menus.pop()
        items = get_menu_items(menu)
        rename_item = next(item for item in items if item.get("label") == "Rename Safe")
        assert rename_item["state"] == "normal"
        labels = [item.get("label") for item in items if item.get("label")]
        assert "Export Safe Proof Zip (planned)" not in labels
        assert "Delete Safe (planned)" not in labels

        # Built-in Safe Right Click
        row_builtin._on_right_click(MagicMock(x_root=100, y_root=100))
        assert window._on_select_calls[-1] == S.SAFE_PREFIX + "builtin_safe"

        assert len(captured_menus) == 1
        menu = captured_menus.pop()
        items = get_menu_items(menu)
        rename_item = next(item for item in items if item.get("label") == "Rename Safe")
        assert rename_item["state"] == "disabled"

        # Verify Shift+F10 also triggers targeting on user safe
        window._on_select_calls.clear()
        row_user.focus_set()
        # Triggering the event callback directly to verify action targets focused row
        row_user._on_right_click(MagicMock(x_root=100, y_root=100))
        assert window._on_select_calls[-1] == S.SAFE_PREFIX + "user_safe"
        assert len(captured_menus) == 1
        captured_menus.clear()

        # 4. Collection context menu
        window._filters.update_collections([
            {"name": "MyCollection", "count": 5}
        ])
        row_col = window._filters._collection_rows[S.COLLECTION_PREFIX + "MyCollection"]
        row_col._on_right_click(MagicMock(x_root=100, y_root=100))

        assert len(captured_menus) == 1
        menu = captured_menus.pop()
        items = get_menu_items(menu)
        labels = [item.get("label") for item in items if item.get("label")]
        assert "View 'MyCollection' Clips" in labels
        assert "Rename Collection…" in labels
