"""Diagnostics module manifest.

Registers under a new global "diagnostics" settings category purely to
supply that category's Live Status card: the crash log (existence-checked,
with an "Open Crash Log" action only when one exists), the real database
path, and a CLI-only pointer to --selftest. Per the real-controls audit
(Q9), selftest must stay a terminal command -- never a UI button/runner.
"""

from __future__ import annotations

from typing import Callable

from .. import ModuleManifest
from ..settings_schema import StatusRow


def _crash_log_path():
    """Mirrors cache_vault.ui.crashlog.log_path() (same %LOCALAPPDATA%\\CacheVault
    base as default_settings_path()). Reuses the existing core helper instead
    of duplicating the LOCALAPPDATA lookup, and stays free of any dependency
    on cache_vault.ui, matching every other module in this package."""
    from ...core.settings import default_settings_path
    return default_settings_path().parent / "crash.log"


def _open_crash_log() -> None:
    from ...core import pathutil
    pathutil.open_file(str(_crash_log_path()))


class DiagnosticsModule(ModuleManifest):
    """Diagnostics — crash log, database path, and the selftest command."""

    def __init__(self, *, db_path_getter: Callable[[], str] | None = None) -> None:
        self._db_path_getter = db_path_getter

    @property
    def id(self) -> str:
        return "diagnostics"

    @property
    def name(self) -> str:
        return "Diagnostics"

    @property
    def description(self) -> str:
        return "Crash log, database path, and the selftest command"

    # --- status rows ---

    def get_status_rows(self) -> list[StatusRow]:
        rows: list[StatusRow] = []

        crash_log_exists = _crash_log_path().is_file()

        def _crash_log_value() -> str:
            return str(_crash_log_path()) if crash_log_exists else "No crashes recorded"

        rows.append(StatusRow(
            "Crash log", _crash_log_value, level="info",
            action_label="Open Crash Log" if crash_log_exists else "",
            action=_open_crash_log if crash_log_exists else None,
        ))

        def _db_path_value() -> str:
            return self._db_path_getter() if self._db_path_getter else "Unavailable"

        rows.append(StatusRow("Database", _db_path_value, level="info"))

        rows.append(StatusRow(
            "Selftest",
            lambda: "Run: python app.py --selftest (terminal only)",
            level="info",
        ))

        return rows
