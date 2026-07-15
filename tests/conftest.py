import os
import sys
from pathlib import Path

import pytest

# Make the repo root importable so ``import cache_vault`` works regardless of
# where pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Never spin up a real system-tray icon during the test suite. pystray's
# Windows backend keeps its own non-daemon message-loop thread whose clean
# shutdown depends on GC/finalizer timing (it can end up blocked deep inside
# a PIL/tkinter finalizer chain triggered from icon-image regeneration) —
# when that happens, threading._shutdown() blocks forever waiting to join
# it, and the whole test process hangs after pytest has already reported
# every test as passed. Set before any test imports cache_vault.ui.shell,
# so every Shell built during the session skips tray-icon creation
# entirely (see cache_vault/ui/tray.py's TrayController.start()). Existing
# scripts (scripts/macro_live_smoke.py, scripts/post_rc3_acceptance_gate.py)
# already opt into this same flag for the same reason; setdefault leaves it
# overridable for anyone deliberately testing the real tray icon.
os.environ.setdefault("CACHE_VAULT_DISABLE_TRAY", "1")

from cache_vault.core.settings import Settings  # noqa: E402
from cache_vault.core.storage import VaultStorage  # noqa: E402
from cache_vault.core.vault import Vault  # noqa: E402
from tests.tk_support import _tcl_unavailable, probe_tk_ui  # noqa: E402


@pytest.fixture(scope="session")
def tk_root():
    """Shared CustomTkinter root for UI tests (one Tcl interpreter per session).

    The probe may pass on runner images where ``import tkinter`` succeeds but
    the Tcl runtime raises at ``CTk()`` construction (e.g. Python 3.11/3.13 on
    windows-2025-vs2026).  A second body-level guard catches those cases.
    """
    ok, reason = probe_tk_ui()
    if not ok:
        pytest.skip(reason or "Tk UI unavailable")
    import customtkinter as ctk
    import tkinter as _tk

    try:
        root = ctk.CTk()
    except _tk.TclError as exc:
        if _tcl_unavailable(exc):
            pytest.skip(f"Tk/CTk runtime unavailable at fixture construction: {exc}")
        raise
    root.withdraw()
    yield root
    try:
        root.destroy()
    except Exception:  # noqa: BLE001
        pass


@pytest.fixture
def storage():
    s = VaultStorage(":memory:")
    yield s
    s.close()


@pytest.fixture
def vault():
    # In-memory DB + default settings that never touch disk.
    v = Vault(storage=VaultStorage(":memory:"), settings=Settings())
    yield v
    v.close()
