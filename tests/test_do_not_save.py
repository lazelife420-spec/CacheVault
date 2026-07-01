from __future__ import annotations

import time
import pytest
import inspect
from cache_vault.core import models
from cache_vault.core.capture_rules import CaptureController
from cache_vault.ui import vault_lock

def test_skip_next_copy_arming_and_clearing(vault):
    ctrl = CaptureController(lambda: vault.settings)
    
    # skip-next-copy arms correctly
    ctrl.arm_ignore_next()
    assert ctrl.ignore_next is True
    
    # skip state can be cleared
    ctrl.cancel_ignore()
    assert ctrl.ignore_next is False


def test_clipboard_events_flow(vault):
    ctrl = CaptureController(lambda: vault.settings)
    
    # Arm skip next
    ctrl.arm_ignore_next()
    assert ctrl.ignore_next is True
    
    # First clipboard event after arming is consumed/ignored
    assert ctrl.consume_ignore() is True
    
    # Second clipboard event is captured normally (ignore state is gone)
    assert ctrl.consume_ignore() is False


def test_skip_state_expiration(vault):
    ctrl = CaptureController(lambda: vault.settings)
    ctrl.arm_ignore_next()
    assert ctrl.ignore_next is True
    
    # Mock time.monotonic to simulate 61 seconds passing
    original_now = ctrl._now
    try:
        ctrl._now = lambda: original_now() + 65.0
        # Check that it expires
        assert ctrl.ignore_next is False
    finally:
        ctrl._now = original_now


def test_existing_capture_behavior_unchanged(vault):
    ctrl = CaptureController(lambda: vault.settings)
    # when not armed, consume_ignore is False
    assert ctrl.consume_ignore() is False


def test_menu_action_wiring_exists():
    # Verify option menu values contain "Do Not Save Next Copy"
    src = inspect.getsource(vault_lock.VaultControlStrip._build)
    assert '"Do Not Save Next Copy"' in src
    
    # Verify choice mapping exists
    src_mapping = inspect.getsource(vault_lock.VaultControlStrip._capture_action)
    assert '"Do Not Save Next Copy": "ignore_next_copy"' in src_mapping


def test_no_crash_on_null_ingest(vault):
    # Verify no crash / safe return on null payload during ingest
    from cache_vault.ui.shell import CacheVaultApp
    app = CacheVaultApp(vault=vault)
    try:
        app._ingest({})
    finally:
        app._quit()
