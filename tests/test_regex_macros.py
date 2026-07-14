"""Tests for Regex Macro Engine."""

from __future__ import annotations

import json
import pytest
from cache_vault.core import models
from cache_vault.core.regex_macros import (
    RegexMacro,
    preview_macro,
    apply_macro,
    build_macro_receipt_payload,
)
from cache_vault.core.settings import Settings
from cache_vault.core.storage import VaultStorage
from cache_vault.core.vault import Vault


def test_macro_preview_valid():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Clean spaces",
        enabled=True,
        pattern=r"\s+",
        replacement=" ",
    )
    res = preview_macro(macro, "hello    world")
    assert res["matched"] is True
    assert res["after"] == "hello world"
    assert res["error"] is None


def test_macro_preview_invalid():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Invalid",
        enabled=True,
        pattern=r"[0-9",
        replacement="",
    )
    res = preview_macro(macro, "hello")
    assert res["matched"] is False
    assert res["error"] is not None
    assert "Invalid regex pattern" in res["error"]


def test_macro_apply_disabled():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Replace hello",
        enabled=False,
        pattern="hello",
        replacement="hi",
    )
    out, transformed = apply_macro(macro, "hello world")
    assert transformed is False
    assert out == "hello world"


def test_macro_apply_scope_content_type():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Scope CT",
        enabled=True,
        pattern="123",
        replacement="456",
        content_types=["code"],
    )
    # Different content type
    out, transformed = apply_macro(macro, "123 text", content_type="plain")
    assert not transformed
    assert out == "123 text"

    # Matching content type
    out, transformed = apply_macro(macro, "123 text", content_type="code")
    assert transformed
    assert out == "456 text"


def test_macro_apply_scope_safe():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Scope Safe",
        enabled=True,
        pattern="123",
        replacement="456",
        safe_scope=["Dev"],
    )
    # Different safe
    out, transformed = apply_macro(macro, "123 text", safe_id="Research")
    assert not transformed
    assert out == "123 text"

    # Matching safe
    out, transformed = apply_macro(macro, "123 text", safe_id="Dev")
    assert transformed
    assert out == "456 text"


def test_macro_apply_scope_source():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Scope Source",
        enabled=True,
        pattern="123",
        replacement="456",
        source_scope=["CLI"],
    )
    # Different source
    out, transformed = apply_macro(macro, "123 text", source="Browser")
    assert not transformed
    assert out == "123 text"

    # Matching source
    out, transformed = apply_macro(macro, "123 text", source="CLI")
    assert transformed
    assert out == "456 text"


def test_macro_receipt_payload():
    macro = RegexMacro(
        macro_id="macro-1",
        name="Macro",
        enabled=True,
        pattern="foo",
        replacement="bar",
    )
    payload = build_macro_receipt_payload(
        macro,
        input_text="foo",
        output_text="bar",
        matched=True,
        transformed=True,
    )
    assert payload["action"] == "macro_transform"
    assert payload["macro_id"] == "macro-1"
    assert payload["matched"] is True
    assert payload["transformed"] is True
    assert "original_sha256" in payload
    assert "output_sha256" in payload
    assert payload["transfer_status"] == "completed"


def test_macro_save_and_load_persistence(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro_list = [
        RegexMacro(
            macro_id="macro-p1",
            name="Persisted Macro",
            enabled=False,
            pattern=r"\d+",
            replacement="NUM",
            content_types=["code"],
            safe_scope=["Dev"],
            source_scope=["CLI"],
        )
    ]

    from cache_vault.core.regex_macros import save_regex_macros, load_regex_macros
    save_regex_macros(macro_list)
    assert test_json.exists()

    loaded = load_regex_macros()
    assert len(loaded) == 1
    m = loaded[0]
    assert m.macro_id == "macro-p1"
    assert m.name == "Persisted Macro"
    assert m.enabled is False
    assert m.pattern == r"\d+"
    assert m.replacement == "NUM"
    assert m.content_types == ["code"]
    assert m.safe_scope == ["Dev"]
    assert m.source_scope == ["CLI"]


def test_macro_load_corrupted_json(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    # Write invalid json structure (corrupted schema)
    test_json.write_text(json.dumps([
        {"macro_id": "corrupted", "name": "Broken"}  # Missing enabled, pattern, replacement
    ]), encoding="utf-8")

    from cache_vault.core.regex_macros import load_regex_macros
    loaded = load_regex_macros()
    assert len(loaded) == 0


def test_disabled_macro_preview_behavior():
    macro = RegexMacro(
        macro_id="macro-d1",
        name="Disabled but Previews",
        enabled=False,  # disabled macro
        pattern="secret",
        replacement="REDACTED",
    )
    # Previews are opt-in, test bench should run preview matching even if disabled!
    res = preview_macro(macro, "my secret key")
    assert res["matched"] is True
    assert res["after"] == "my REDACTED key"


def test_capture_applies_macros_integration(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro = RegexMacro(
        macro_id="macro-c1",
        name="Redact IP",
        enabled=True,
        pattern=r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        replacement="[REDACTED IP]",
        content_types=["plain"],
        safe_scope=["Dev"],
    )
    from cache_vault.core.regex_macros import save_regex_macros
    save_regex_macros([macro])

    settings = Settings()
    settings.user_safes.append({"id": "Dev", "name": "Dev", "icon": "💼", "accent": "blue"})
    storage = VaultStorage(":memory:")
    vault = Vault(storage, settings)

    clip = vault.capture("connect to 192.168.1.1 now", safe_id="Dev")
    assert clip is not None
    assert clip.content == "connect to 192.168.1.1 now"

    clips = storage.list_clips()
    assert len(clips) == 2

    transformed = [c for c in clips if c.id != clip.id][0]
    assert transformed.content == "connect to [REDACTED IP] now"
    assert transformed.duplicate_of == clip.id
    assert "macro-transformed" in transformed.tags
    assert f"original:{clip.id}" in transformed.tags
    assert transformed.title == "[Macro: Redact IP] connect to 192.168.1.1 now"

    events = vault.events.recent()
    macro_evts = [e for e in events if e["event_type"] == "macro_transform"]
    assert len(macro_evts) == 1
    evt = macro_evts[0]
    assert evt["details"]["macro_id"] == "macro-c1"
    assert evt["details"]["original_clip_id"] == clip.id
    assert evt["details"]["transformed_clip_id"] == transformed.id
    assert evt["details"]["matched"] is True
    assert evt["details"]["transformed"] is True


def test_capture_applies_macros_disabled(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro = RegexMacro(
        macro_id="macro-c2",
        name="Redact IP",
        enabled=False,
        pattern=r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        replacement="[REDACTED IP]",
    )
    from cache_vault.core.regex_macros import save_regex_macros
    save_regex_macros([macro])

    storage = VaultStorage(":memory:")
    vault = Vault(storage, Settings())

    clip = vault.capture("connect to 192.168.1.1 now")
    assert clip is not None
    assert clip.content == "connect to 192.168.1.1 now"

    clips = storage.list_clips()
    assert len(clips) == 1


def test_capture_applies_macros_unmatched_or_invalid(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro_unmatched = RegexMacro(
        macro_id="macro-c3",
        name="Redact IP",
        enabled=True,
        pattern=r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        replacement="[REDACTED IP]",
    )
    macro_invalid = RegexMacro(
        macro_id="macro-c4",
        name="Invalid Pattern",
        enabled=True,
        pattern=r"[0-9",
        replacement="",
    )
    from cache_vault.core.regex_macros import save_regex_macros
    save_regex_macros([macro_unmatched, macro_invalid])

    storage = VaultStorage(":memory:")
    vault = Vault(storage, Settings())

    clip = vault.capture("no IP addresses here")
    assert clip is not None

    clips = storage.list_clips()
    assert len(clips) == 1

    events = vault.events.recent()
    warnings = [e for e in events if e["event_type"] == "macro_warning"]
    assert len(warnings) == 1
    assert warnings[0]["details"]["macro_id"] == "macro-c4"
    assert "Invalid regex pattern" in warnings[0]["details"]["error"]


def test_capture_applies_macros_scope_mismatch(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro = RegexMacro(
        macro_id="macro-c5",
        name="Redact IP",
        enabled=True,
        pattern=r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}",
        replacement="[REDACTED IP]",
        safe_scope=["Dev"],
    )
    from cache_vault.core.regex_macros import save_regex_macros
    save_regex_macros([macro])

    storage = VaultStorage(":memory:")
    vault = Vault(storage, Settings())

    clip = vault.capture("connect to 192.168.1.1 now")
    assert clip is not None

    clips = storage.list_clips()
    assert len(clips) == 1


def test_dialog_status_resolution():
    macro_disabled = RegexMacro(
        macro_id="m1", name="Disabled", enabled=False, pattern="foo", replacement="bar"
    )
    macro_invalid = RegexMacro(
        macro_id="m2", name="Invalid", enabled=True, pattern="[0-9", replacement="bar"
    )
    macro_live = RegexMacro(
        macro_id="m3", name="Live", enabled=True, pattern="foo", replacement="bar"
    )

    from cache_vault.ui.regex_macro_dialog import RegexMacroDialog
    from unittest.mock import MagicMock
    dialog = MagicMock()
    
    status_disabled = RegexMacroDialog._get_macro_status(dialog, macro_disabled)
    status_invalid = RegexMacroDialog._get_macro_status(dialog, macro_invalid)
    status_live = RegexMacroDialog._get_macro_status(dialog, macro_live)

    assert status_disabled == "DISABLED"
    assert status_invalid == "INVALID"
    assert status_live == "LIVE"


def test_disable_all_macros_action(tmp_path, monkeypatch):
    test_json = tmp_path / "regex_macros.json"
    monkeypatch.setattr("cache_vault.core.regex_macros.regex_macros_path", lambda: test_json)

    macro_list = [
        RegexMacro(macro_id="m1", name="Macro 1", enabled=True, pattern="foo", replacement="bar"),
        RegexMacro(macro_id="m2", name="Macro 2", enabled=True, pattern="foo", replacement="bar"),
    ]
    from cache_vault.core.regex_macros import save_regex_macros, load_regex_macros
    save_regex_macros(macro_list)

    from tkinter import messagebox
    monkeypatch.setattr(messagebox, "askyesno", lambda *args, **kwargs: True)

    from unittest.mock import MagicMock
    from cache_vault.ui.regex_macro_dialog import RegexMacroDialog
    
    dialog = MagicMock()
    dialog._macros = load_regex_macros()
    dialog._selected_macro = dialog._macros[0]
    
    RegexMacroDialog._on_disable_all(dialog)

    assert all(m.enabled is False for m in dialog._macros)
    
    loaded = load_regex_macros()
    assert all(m.enabled is False for m in loaded)



