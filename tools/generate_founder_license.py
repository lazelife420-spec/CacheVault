#!/usr/bin/env python3
"""Generate a signed Cache Vault Founder license file.

The private signing key must live outside the repository. Only the matching
public key is embedded in the application.

Example::

    python tools/generate_founder_license.py ^
      --licensee buyer@example.com ^
      --private-key C:\\secure\\cachevault_founder_private.pem ^
      --out C:\\licenses\\buyer-founder-license.json

Generate a new development keypair (keep the private PEM secure)::

    python tools/generate_founder_license.py --generate-keypair --out-dir C:\\secure
"""

from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives import serialization

from cache_vault.licensing import EDITION_FOUNDER, FOUNDER_FEATURES, PRODUCT_ID


def _canonical_payload_bytes(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_private_key(path: Path) -> Ed25519PrivateKey:
    data = path.read_bytes()
    key = serialization.load_pem_private_key(data, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise SystemExit(f"Expected Ed25519 private key: {path}")
    return key


def _sign_payload(payload: dict, private_key: Ed25519PrivateKey) -> str:
    sig = private_key.sign(_canonical_payload_bytes(payload))
    return base64.b64encode(sig).decode("ascii")


def generate_keypair(out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    key = Ed25519PrivateKey.generate()
    priv_path = out_dir / "cachevault_founder_private.pem"
    pub_path = out_dir / "cachevault_founder_public.pem"
    priv_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    pub_path.write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
    )
    print(f"Wrote private key: {priv_path}")
    print(f"Wrote public key:  {pub_path}")
    print("Embed the public key in cache_vault/licensing.py for production signing.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a signed Founder license.")
    parser.add_argument("--licensee", help="Buyer email or name")
    parser.add_argument("--edition", default=EDITION_FOUNDER, help="License edition")
    parser.add_argument("--private-key", type=Path, help="Path to Ed25519 private PEM")
    parser.add_argument("--out", type=Path, help="Output license.json path")
    parser.add_argument(
        "--expires-at",
        default=None,
        help="Optional ISO8601 expiry (default: lifetime / null)",
    )
    parser.add_argument(
        "--generate-keypair",
        action="store_true",
        help="Generate a new dev keypair in --out-dir",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path.home() / ".cachevault-keys",
        help="Directory for --generate-keypair output",
    )
    args = parser.parse_args(argv)

    if args.generate_keypair:
        generate_keypair(args.out_dir)
        return 0

    if not args.licensee or not args.private_key or not args.out:
        parser.error("--licensee, --private-key, and --out are required unless --generate-keypair")

    private_key = _load_private_key(args.private_key)
    issued_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "product": PRODUCT_ID,
        "edition": args.edition,
        "licensee": args.licensee,
        "issued_at": issued_at,
        "expires_at": args.expires_at,
        "features": sorted(FOUNDER_FEATURES),
    }
    doc = dict(payload)
    doc["signature"] = _sign_payload(payload, private_key)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote license: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
