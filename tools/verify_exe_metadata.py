"""Verify Cache Vault Windows exe metadata and version consistency."""

from __future__ import annotations

import argparse
import re
import sys
import tomllib
from pathlib import Path

import win32api

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cache_vault import __product__, __version__  # noqa: E402
from cache_vault.build_meta import windows_version_strings, windows_version_tuple  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", required=True, help="Path to CacheVault.exe")
    return parser.parse_args()


def hiword(value: int) -> int:
    return value >> 16


def loword(value: int) -> int:
    return value & 0xFFFF


def load_pyproject_version() -> str:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def first_match(path: Path, pattern: str) -> str | None:
    match = re.search(pattern, path.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def read_version_strings(exe_path: Path) -> dict[str, str]:
    translations = win32api.GetFileVersionInfo(str(exe_path), r"\VarFileInfo\Translation")
    if translations:
        lang, codepage = translations[0]
    else:
        lang, codepage = 1033, 1200

    values = {}
    for key in windows_version_strings():
        query = rf"\StringFileInfo\{lang:04X}{codepage:04X}\{key}"
        values[key] = win32api.GetFileVersionInfo(str(exe_path), query)
    return values


def main() -> int:
    args = parse_args()
    exe_path = Path(args.exe).resolve()
    ok = True

    if not exe_path.exists():
        raise SystemExit(f"FAIL  missing executable: {exe_path}")

    pyproject_version = load_pyproject_version()
    if pyproject_version == __version__:
        print(f"PASS  source versions agree: {__version__}")
    else:
        ok = False
        print(f"FAIL  pyproject version {pyproject_version!r} != package version {__version__!r}")

    readme_version = first_match(ROOT / "README.md", r"MVP v(\d+\.\d+\.\d+)")
    if readme_version is None:
        print("INFO  README has no explicit MVP version marker")
    elif readme_version == __version__:
        print(f"PASS  README version marker matches: {readme_version}")
    else:
        ok = False
        print(f"FAIL  README version marker {readme_version!r} != {__version__!r}")

    notes_version = first_match(ROOT / "RELEASE_NOTES.md", r"^# Cache Vault v(\d+\.\d+\.\d+)")
    if notes_version is None:
        print("INFO  RELEASE_NOTES.md has no version heading")
    elif notes_version == __version__:
        print(f"PASS  release notes version matches: {notes_version}")
    else:
        ok = False
        print(f"FAIL  release notes version {notes_version!r} != {__version__!r}")

    fixed = win32api.GetFileVersionInfo(str(exe_path), "\\")
    fixed_file = (
        hiword(fixed["FileVersionMS"]),
        loword(fixed["FileVersionMS"]),
        hiword(fixed["FileVersionLS"]),
        loword(fixed["FileVersionLS"]),
    )
    fixed_product = (
        hiword(fixed["ProductVersionMS"]),
        loword(fixed["ProductVersionMS"]),
        hiword(fixed["ProductVersionLS"]),
        loword(fixed["ProductVersionLS"]),
    )
    expected_tuple = windows_version_tuple()
    if fixed_file == expected_tuple and fixed_product == expected_tuple:
        print(f"PASS  fixed file/product version matches: {expected_tuple}")
    else:
        ok = False
        print(
            "FAIL  fixed version mismatch: "
            f"file={fixed_file} product={fixed_product} expected={expected_tuple}"
        )

    strings = read_version_strings(exe_path)
    expected_strings = windows_version_strings()
    for key, expected in expected_strings.items():
        actual = strings.get(key)
        if actual == expected:
            print(f"PASS  {key}={actual}")
        else:
            ok = False
            print(f"FAIL  {key}={actual!r} expected {expected!r}")

    if strings.get("ProductName") != __product__:
        ok = False
        print(f"FAIL  ProductName mismatch against source product {__product__!r}")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
