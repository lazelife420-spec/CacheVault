"""Shared build/release metadata helpers."""

from __future__ import annotations

from . import (
    __company__,
    __copyright__,
    __description__,
    __product__,
    __version__,
)

INTERNAL_NAME = "CacheVault"
ORIGINAL_FILENAME = "CacheVault.exe"


def windows_version_tuple(version: str = __version__) -> tuple[int, int, int, int]:
    parts = version.split(".")
    if not 1 <= len(parts) <= 4:
        raise ValueError(f"Unsupported version format: {version!r}")
    try:
        values = [int(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"Version must contain only integers: {version!r}") from exc
    while len(values) < 4:
        values.append(0)
    return tuple(values)


def windows_version_strings() -> dict[str, str]:
    return {
        "CompanyName": __company__,
        "FileDescription": __description__,
        "FileVersion": __version__,
        "InternalName": INTERNAL_NAME,
        "LegalCopyright": __copyright__,
        "OriginalFilename": ORIGINAL_FILENAME,
        "ProductName": __product__,
        "ProductVersion": __version__,
    }
