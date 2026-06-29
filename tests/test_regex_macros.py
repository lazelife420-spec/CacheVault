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


def test_no_live_capture_applies_macros():
    # Make sure we don't accidentally import or invoke regex_macros in vault.py/shell.py yet.
    # Let's inspect vault.py's capture methods to verify they don't call apply_macro.
    from pathlib import Path
    vault_py = Path(__file__).parent.parent / "cache_vault" / "core" / "vault.py"
    content = vault_py.read_text(encoding="utf-8")
    assert "apply_macro" not in content
    assert "regex_macros" not in content

