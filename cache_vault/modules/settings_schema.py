"""Declarative settings-schema types for the module system.

Modules return ``SettingsCategory`` / ``SettingsField`` objects to describe
what settings they own.  ``StatusRow`` describes live status indicators.
The Settings Hub (future chunk) renders these; tests validate them against
the real ``Settings`` dataclass right now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

# Valid field_type values understood by the future Settings Hub renderer.
FIELD_TYPES = frozenset({"toggle", "text", "number", "choice", "hotkey", "readonly"})

# Mapping: field_type -> acceptable Python types on the Settings dataclass.
_FIELD_TYPE_TO_PYTHON: dict[str, tuple[type, ...]] = {
    "toggle": (bool,),
    "text": (str, list),  # list[str] rendered as newline-separated textarea
    "number": (int, float),
    "choice": (str,),
    "hotkey": (str,),
    "readonly": (str, int, float, bool, list),  # permissive for display-only
}


@dataclass
class SettingsField:
    """One user-facing setting backed by a ``Settings`` dataclass field."""

    key: str
    label: str
    field_type: str  # one of FIELD_TYPES
    description: str = ""
    group: str = ""
    default: Any = None
    choices: list[str] | None = None
    min_val: int | float | None = None
    max_val: int | float | None = None


@dataclass
class SettingsCategory:
    """A group of related settings shown together in the sidebar."""

    id: str
    label: str
    icon: str = ""
    fields: list[SettingsField] = field(default_factory=list)


@dataclass
class StatusRow:
    """A live status indicator shown in the settings panel."""

    label: str
    value_getter: Callable[[], str]
    level: str = "info"  # info | ok | warning | error
    action_label: str = ""
    action: Callable[[], None] | None = None


# ---------------------------------------------------------------------------
# Schema validation helper
# ---------------------------------------------------------------------------

def validate_schema_against_settings(
    categories: list[SettingsCategory],
    settings_cls: type,
) -> list[str]:
    """Check every ``SettingsField.key`` exists on *settings_cls* with a
    sensible Python type for its declared ``field_type``.

    Returns a list of error strings (empty = valid).
    """
    known_fields: dict[str, type] = {}
    for f_name, f_default in settings_cls.__dataclass_fields__.items():
        known_fields[f_name] = f_default.type if isinstance(f_default.type, type) else None

    # Re-resolve types from annotations (handles forward refs / string annotations).
    import typing
    hints = typing.get_type_hints(settings_cls)

    errors: list[str] = []
    for cat in categories:
        for sf in cat.fields:
            if sf.field_type not in FIELD_TYPES:
                errors.append(
                    f"{cat.id}/{sf.key}: unknown field_type '{sf.field_type}'"
                )
                continue
            if sf.key not in hints:
                errors.append(
                    f"{cat.id}/{sf.key}: key does not exist on {settings_cls.__name__}"
                )
                continue
            python_type = hints[sf.key]
            # Unwrap Optional / generic aliases to their origin.
            origin = getattr(python_type, "__origin__", None)
            if origin is not None:
                python_type = origin
            allowed = _FIELD_TYPE_TO_PYTHON.get(sf.field_type, ())
            if allowed and python_type not in allowed:
                errors.append(
                    f"{cat.id}/{sf.key}: field_type '{sf.field_type}' expects "
                    f"{allowed} but Settings has {python_type}"
                )
    return errors
