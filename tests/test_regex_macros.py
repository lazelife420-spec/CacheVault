"""Tests for Regex Macro Engine."""

from __future__ import annotations

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
