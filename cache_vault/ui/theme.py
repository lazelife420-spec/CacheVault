"""Proof Foundry theme helpers for CustomTkinter widgets."""

from __future__ import annotations

import sys
import tkinter
import weakref
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
        "hover_color": ("#B0B8BC", brand.VAULT_BORDER),
        "border_width": 1,
        "border_color": brand.VAULT_CARD_BORDER,
        "text_color": (brand.FOUNDRY_BLACK, brand.RECEIPT_WHITE),
        **extra,
    }


def quiet_button(**extra) -> dict:
    """Ghost action — transparent surface, muted text, hairline hover.

    For low-frequency actions that must stay reachable without competing
    with the primary action (card action bars, row affordances)."""
    return {
        "fg_color": "transparent",
        "hover_color": ("#C8D0D4", "#232B33"),
        "text_color": brand.MUTED_FG,
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
    return ("#B8D4CE", "#1A2E2A")


def nav_hover_bg() -> tuple[str, str]:
    return ("#D0D8DA", "#222830")


def section_heading(**extra) -> dict:
    return {
        "text_color": brand.STAMP_GOLD,
        "font": font(size=12, weight="bold"),
        **extra,
    }


def vault_card(**extra) -> dict:
    """Sealed vault panel — subtle border, graphite surface."""
    return {
        "fg_color": brand.SURFACE_BG,
        "corner_radius": 8,
        "border_width": 1,
        "border_color": brand.VAULT_CARD_BORDER,
        **extra,
    }


def status_badge_fg(verified: bool = False) -> str:
    return brand.PROOF_TEAL if verified else brand.STAMP_GOLD


# Per-interpreter font caches. A CTkFont is bound to the Tk interpreter that
# was current when it was created, so a font from a destroyed root must never
# be handed to a widget under a new one ("application has been destroyed").
_FONT_CACHE_BY_ROOT: "weakref.WeakKeyDictionary[object, dict[tuple, ctk.CTkFont]]" = (
    weakref.WeakKeyDictionary()
)
# Strong refs to every font ever handed out, held for process lifetime on
# purpose: see (1) in font(). Dropping one makes it garbage, which is exactly
# the finalizer hazard the cache exists to avoid. Bounded by
# (roots x variants), a handful in the app and ~one per root under test.
_FONT_KEEPALIVE: list[ctk.CTkFont] = []


def font(
    *,
    family: str | None = None,
    size: int | None = None,
    weight: str | None = None,
) -> ctk.CTkFont:
    """Return a shared CTkFont for this (family, size, weight).

    Row/card builders ask for the same handful of font variants thousands of
    times per render.  Two reasons these must be cached rather than
    constructed per widget:

    1.  Every CTkFont is a tkinter.font.Font whose __del__ calls into Tk
        ("font delete").  Discarded fonts are therefore Tk work performed on
        whichever thread the garbage collector happens to run on, and
        tkinter.font.Font.__del__ swallows the resulting error rather than
        raising -- so an off-main-thread finalizer does not fail loudly, it
        blocks on the Tcl interpreter.  A render that orphans ~1,300 fonts
        while the refresh worker is mid-query can land that finalizer on the
        worker thread and hang the refresh (observed as "refresh did not
        settle", worker stuck inside storage.counts).  A cached font is never
        garbage, so the finalizer never runs.
    2.  Constructing one costs a Tcl "font create" round-trip per widget.

    Sharing an instance across widgets is safe: CTk widgets register a size
    callback on the font in __init__ and deregister it in destroy(), so the
    callback list tracks live widgets only.  Callers must not mutate the
    returned font via configure() -- assign a different font instead.
    """
    root = tkinter._default_root
    per_root = _FONT_CACHE_BY_ROOT.get(root)
    if per_root is None:
        per_root = {}
        try:
            _FONT_CACHE_BY_ROOT[root] = per_root
        except TypeError:
            # No root yet (or not weak-referenceable): fall back to an
            # uncached font rather than binding it to the wrong interpreter.
            per_root = None

    key = (family, size, weight)
    if per_root is not None:
        cached = per_root.get(key)
        if cached is not None:
            return cached

    kwargs = {}
    if family is not None:
        kwargs["family"] = family
    if size is not None:
        kwargs["size"] = size
    if weight is not None:
        kwargs["weight"] = weight
    created = ctk.CTkFont(**kwargs)
    _FONT_KEEPALIVE.append(created)
    if per_root is not None:
        per_root[key] = created
    return created


def body_font(size: int = 12) -> ctk.CTkFont:
    return font(size=size)


def meta_font(size: int = 10) -> ctk.CTkFont:
    """Small metadata/caption role (timestamps, source lines, hints)."""
    return font(size=size)


def heading_font(size: int = 15, weight: str = "bold") -> ctk.CTkFont:
    """Card/section heading role."""
    return font(size=size, weight=weight)


def mono_font(size: int = 11) -> ctk.CTkFont:
    return font(family="Consolas", size=size)


def segmented_active(**extra) -> dict:
    return primary_button(**extra)


def segmented_inactive(**extra) -> dict:
    return {
        "fg_color": ("#D0D6DA", "#1A2229"),
        "hover_color": ("#B8C0C6", "#263038"),
        "text_color": brand.MUTED_FG,
        **extra,
    }
