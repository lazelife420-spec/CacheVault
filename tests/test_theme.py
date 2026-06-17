"""Proof Foundry CTk theme must include every key CustomTkinter expects."""

import json

from cache_vault.ui.theme import theme_json_path


def test_proof_foundry_theme_has_required_keys():
    with open(theme_json_path(), encoding="utf-8") as f:
        theme = json.load(f)
    # Keys present in upstream customtkinter blue.json — our theme must match.
    required = {
        "CTk", "CTkToplevel", "CTkFrame", "CTkButton", "CTkLabel", "CTkEntry",
        "CTkCheckBox", "CTkSwitch", "CTkRadioButton", "CTkProgressBar",
        "CTkSlider", "CTkOptionMenu", "CTkComboBox", "CTkScrollbar",
        "CTkSegmentedButton", "CTkTextbox", "CTkScrollableFrame",
        "DropdownMenu", "CTkFont",
    }
    missing = required - set(theme.keys())
    assert not missing, f"proof_foundry.json missing: {sorted(missing)}"
    assert "Windows" in theme["CTkFont"]
