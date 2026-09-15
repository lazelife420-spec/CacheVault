"""Regression and atomic persistence test for DEF-003: Regex Macro Crash-Safe Save."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from cache_vault.core import regex_macros
from cache_vault.core.regex_macros import RegexMacro, load_regex_macros, save_regex_macros


def test_regex_macros_save_load_roundtrip():
    """Verify normal save and load round-trip with multiple macros."""
    with tempfile.TemporaryDirectory() as tmpdir:
        macro_file = Path(tmpdir) / "regex_macros.json"
        with patch.object(regex_macros, "regex_macros_path", return_value=macro_file):
            m1 = RegexMacro(macro_id="m1", name="Redact Email", enabled=True, pattern=r"[\w\.-]+@[\w\.-]+", replacement="[REDACTED_EMAIL]")
            m2 = RegexMacro(macro_id="m2", name="Redact SSN", enabled=False, pattern=r"\b\d{3}-\d{2}-\d{4}\b", replacement="[REDACTED_SSN]")

            save_regex_macros([m1, m2])

            assert macro_file.exists()
            content = macro_file.read_text(encoding="utf-8")
            data = json.loads(content)
            assert len(data) == 2
            assert data[0]["macro_id"] == "m1"
            assert data[1]["macro_id"] == "m2"

            loaded = load_regex_macros()
            assert len(loaded) == 2
            assert loaded[0].name == "Redact Email"
            assert loaded[0].enabled is True
            assert loaded[1].enabled is False


def test_regex_macros_atomic_preservation_on_failure():
    """Verify existing macro file is preserved if write raises before atomic replacement."""
    with tempfile.TemporaryDirectory() as tmpdir:
        macro_file = Path(tmpdir) / "regex_macros.json"
        with patch.object(regex_macros, "regex_macros_path", return_value=macro_file):
            original_m = RegexMacro(macro_id="orig", name="Original", enabled=True, pattern="foo", replacement="bar")
            save_regex_macros([original_m])

            original_text = macro_file.read_text(encoding="utf-8")

            # Simulate an error during atomic temp file creation or write
            new_m = RegexMacro(macro_id="new", name="New", enabled=True, pattern="x", replacement="y")
            with patch("cache_vault.core.safe_io.tempfile.mkstemp", side_effect=OSError("Disk write error")):
                save_regex_macros([new_m])

            # Original file MUST remain intact
            assert macro_file.exists()
            assert macro_file.read_text(encoding="utf-8") == original_text
