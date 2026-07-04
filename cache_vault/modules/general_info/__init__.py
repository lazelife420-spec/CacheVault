"""General info module manifest.

Registers under the existing global "general" settings category (not a new
sidebar entry — ``get_settings_schema()`` stays at the ABC default of ``[]``)
purely to supply that category's Live Status card: version/release, whether
this is a packaged build or a source checkout, the app data folder (with an
"Open Data Folder" action), and an optional "Show first-use guide again"
action when the shell provides one.
"""

from __future__ import annotations

import sys
from typing import Callable

from .. import ModuleManifest
from ..settings_schema import StatusRow


def _version_line() -> str:
    """Human-readable version/build string, e.g. 'Version 0.1.4 · Public Release'.

    Mirrors ``cache_vault.ui.dialogs.version_line()``. Duplicated (not
    imported) to keep ``cache_vault.modules`` free of any dependency on
    ``cache_vault.ui``, matching every other module in this package.
    """
    from ... import __release_label__, __version__

    label = (__release_label__ or "").strip()
    base = f"Version {__version__}"
    return f"{base} \u00b7 {label}" if label else base


def _open_data_folder() -> None:
    from ...core import pathutil
    from ...core.settings import default_settings_path

    folder = default_settings_path().parent
    folder.mkdir(parents=True, exist_ok=True)
    pathutil.open_path(str(folder))


class GeneralInfoModule(ModuleManifest):
    """General — version/build info, data folder, and first-use guide."""

    def __init__(self, *, show_guide_action: Callable[[], None] | None = None) -> None:
        self._show_guide_action = show_guide_action

    @property
    def id(self) -> str:
        return "general"

    @property
    def name(self) -> str:
        return "General"

    @property
    def description(self) -> str:
        return "App version, data folder, and first-use guide"

    # --- status rows ---

    def get_status_rows(self) -> list[StatusRow]:
        rows: list[StatusRow] = []

        rows.append(StatusRow("Version", _version_line, level="info"))

        def _running_from() -> str:
            return "Packaged build" if getattr(sys, "_MEIPASS", None) is not None else "Running from source"

        rows.append(StatusRow("Running from", _running_from, level="info"))

        def _data_folder() -> str:
            from ...core.settings import default_settings_path
            return str(default_settings_path().parent)

        rows.append(StatusRow(
            "Data folder", _data_folder, level="info",
            action_label="Open Data Folder", action=_open_data_folder,
        ))

        rows.append(StatusRow(
            "First-use guide",
            lambda: "Explains receipts, Safes, Mobile Inbox, and exports",
            level="info",
            action_label="Show first-use guide again" if self._show_guide_action else "",
            action=self._show_guide_action,
        ))

        return rows
