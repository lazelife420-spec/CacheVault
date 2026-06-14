"""Verify the structure and checksum of a packaged Cache Vault release zip.

Checks:
  1. zip filename includes the provided tag
  2. CacheVault.exe is present
  3. RELEASE_NOTES.md or README.md is present
  4. source-only junk is not present in the zip
  5. SHA256SUMS.txt exists separately and matches the zip hash
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path, PurePosixPath
import zipfile

FORBIDDEN_PARTS = {
    ".git",
    ".github",
    "__pycache__",
    "assets",
    "build",
    "cache_vault",
    "dist",
    "packaging",
    "tests",
    "tools",
}
FORBIDDEN_SUFFIXES = {".py", ".pyc", ".pyo", ".ps1", ".spec"}
DOC_NAMES = {"README.md", "RELEASE_NOTES.md"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", dest="zip_path", required=True)
    parser.add_argument("--sha256", dest="sha_path", required=True)
    parser.add_argument("--tag", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    zip_path = Path(args.zip_path)
    sha_path = Path(args.sha_path)
    tag = args.tag
    ok = True

    if not zip_path.exists():
        raise SystemExit(f"FAIL  missing zip artifact: {zip_path}")
    if not sha_path.exists():
        raise SystemExit(f"FAIL  missing checksum file: {sha_path}")

    expected_zip_name = f"CacheVault-{tag}-windows.zip"
    if zip_path.name != expected_zip_name:
        ok = False
        print(f"FAIL  zip name does not match expected artifact name: {zip_path.name}")
    else:
        print(f"PASS  zip name matches expected artifact name: {zip_path.name}")

    if sha_path.name != "SHA256SUMS.txt":
        ok = False
        print(f"FAIL  checksum file must be named SHA256SUMS.txt: {sha_path.name}")
    else:
        print("PASS  checksum file is generated separately as SHA256SUMS.txt")

    with zipfile.ZipFile(zip_path) as zf:
        names = [name for name in zf.namelist() if not name.endswith("/")]

    basenames = {PurePosixPath(name).name for name in names}
    if "CacheVault.exe" not in basenames:
        ok = False
        print("FAIL  release zip is missing CacheVault.exe")
    else:
        print("PASS  release zip contains CacheVault.exe")

    docs_found = sorted(DOC_NAMES.intersection(basenames))
    if not docs_found:
        ok = False
        print("FAIL  release zip is missing README.md or RELEASE_NOTES.md")
    else:
        print(f"PASS  release zip contains release documentation: {docs_found}")

    junk = []
    for name in names:
        path = PurePosixPath(name)
        if len(path.parts) != 1:
            junk.append(name)
            continue
        if any(part in FORBIDDEN_PARTS for part in path.parts):
            junk.append(name)
            continue
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            junk.append(name)
    junk = [name for name in junk if PurePosixPath(name).name != "CacheVault.exe"]

    if junk:
        ok = False
        print("FAIL  release zip contains source-only junk:")
        for name in junk:
            print(f"        - {name}")
    else:
        print("PASS  release zip contains only packaged files")

    entries = {}
    for line in sha_path.read_text(encoding="ascii").splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 1)
        if len(parts) != 2:
            ok = False
            print(f"FAIL  malformed checksum line: {line}")
            continue
        entries[parts[1].strip()] = parts[0].strip().lower()

    expected_hash = entries.get(zip_path.name)
    actual_hash = sha256_file(zip_path)
    if expected_hash is None:
        ok = False
        print(f"FAIL  checksum file is missing an entry for {zip_path.name}")
    elif expected_hash != actual_hash:
        ok = False
        print(f"FAIL  checksum mismatch for {zip_path.name}")
    else:
        print(f"PASS  checksum matches SHA256SUMS.txt for {zip_path.name}")

    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
