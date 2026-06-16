"""Proof Foundry theme helpers for CustomTkinter widgets."""

from __future__ import annotations

import sys
from pathlib import Path

import customtkinter as ctk

from .. import brand


def theme_json_path() -> Path:
    """Resolve the Proof Foundry CTk theme (dev checkout or PyInstaller bundle)."""
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "cache_vault" / "ui" / "themes" / "proof_foundry.json"
    return Path(__file__).resolve().parent / "themes" / "proof_foundry.json"


def apply_app_theme() -> None:
    """Register the Proof Foundry palette as the default CTk theme."""
    import customtkinter as ctk

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme(str(theme_json_path()))


def primary_button(**extra) -> dict:
    """Proof Teal — primary actions and verified/export states."""
    return {
        "fg_color": brand.PROOF_TEAL,
        "hover_color": brand.PROOF_TEAL_HOVER,
        "text_color": brand.FOUNDRY_BLACK,
        **extra,
    }


def secondary_button(**extra) -> dict:
    """Iron Gray — neutral chrome actions."""
    return {
        "fg_color": ("#C8D0D4", brand.IRON_GRAY),
        "hover_color": ("#B0B8BC", "#263038"),
        "text_color": (brand.FOUNDRY_BLACK, brand.RECEIPT_WHITE),
        **extra,
    }


def destructive_button(**extra) -> dict:
    """Warning Red — permanent removal and destructive warnings."""
    return {
        "fg_color": brand.WARNING_RED,
        "hover_color": brand.WARNING_RED_HOVER,
        "text_color": brand.RECEIPT_WHITE,
        **extra,
    }


def proof_badge_fg() -> str:
    """Stamp Gold — receipt/proof accents (sparingly)."""
    return brand.STAMP_GOLD


def nav_active_bg() -> tuple[str, str]:
    return ("#9FE8DC", "#1E4A44")


def nav_hover_bg() -> tuple[str, str]:
    return ("#D8ECE8", "#2A343C")


def section_heading(**extra) -> dict:
    return {
        "text_color": brand.PROOF_TEAL,
        "font": ctk.CTkFont(size=12, weight="bold"),
        **extra,
    }


def body_font(size: int = 12) -> ctk.CTkFont:
    import customtkinter as ctk
    return ctk.CTkFont(size=size)


def mono_font(size: int = 11) -> ctk.CTkFont:
    import customtkinter as ctk
    return ctk.CTkFont(family="Consolas", size=size)


def segmented_active(**extra) -> dict:
    return primary_button(**extra)


def segmented_inactive(**extra) -> dict:
    return {
        "fg_color": ("#D0D6DA", "#1A2229"),
        "hover_color": ("#B8C0C6", "#263038"),
        "text_color": brand.MUTED_FG,
        **extra,
    }
