"""Cache Vault Developer CLI.

Push text, URLs, and files directly to Cache Vault via local bridge.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path


def load_bridge_config() -> tuple[str, int, bool]:
    """Load port, bind host, and enabled status from Cache Vault settings."""
    try:
        from cache_vault.core.settings import Settings
        settings = Settings.load()
        port = settings.mobile_access_port or 8742
        host = settings.mobile_access_bind_host or "127.0.0.1"
        host = host.strip()
        if not host or host == "0.0.0.0":
            host = "127.0.0.1"
        enabled = bool(settings.mobile_access_enabled)
        return host, port, enabled
    except Exception:
        return "127.0.0.1", 8742, False


def get_auth_token_or_pair() -> tuple[str, str]:
    """Retrieve existing token config or pair CLI automatically as a local device."""
    config_path = Path.home() / ".cache_vault_cli.json"

    # Avoid import side-effects until active
    from cache_vault.core.settings import Settings
    from cache_vault.core import models
    from cache_vault.core.mobile.models import PairedDevice, new_device_token, hash_token

    settings = Settings.load()

    config = {}
    if config_path.exists():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    device_id = config.get("device_id")
    token = config.get("token")

    device_paired = False
    if device_id and token:
        th = hash_token(token)
        for raw in settings.paired_devices:
            d = PairedDevice.from_dict(raw)
            if d.device_id == device_id and d.token_hash == th and d.revoked_at is None:
                device_paired = True
                break

    if not device_paired:
        # Automatically pair the CLI locally
        device_id = models.CLI_DEVICE_ID
        token = new_device_token()
        device = PairedDevice(
            device_id=device_id,
            device_name=models.CLI_DEVICE_NAME,
            created_at=models.now_iso(),
            token_hash=hash_token(token),
        )
        # Clear out any existing duplicate CLI device configurations
        settings.paired_devices = [
            d for d in settings.paired_devices
            if d.get("device_id") != models.CLI_DEVICE_ID
        ]
        settings.paired_devices.append(device.to_dict())
        settings.save()

        # Save plaintext token in CLI user directory
        config = {"device_id": device_id, "token": token}
        try:
            config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
            print(f"Info: First-time auto-pairing completed. CLI paired config saved to {config_path}")
        except OSError as e:
            print(f"Warning: Could not save local CLI config: {e}", file=sys.stderr)

    return str(device_id), str(token)


def get_latest_receipt() -> dict | None:
    """Read the most recently written local JSON receipt file from disk that belongs to CLI."""
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    receipts_root = Path(base) / "CacheVault" / "Receipts"
    if not receipts_root.exists():
        return None

    json_files = list(receipts_root.glob("**/*.json"))
    if not json_files:
        return None

    # Sort files by last modification timestamp descending
    json_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    
    for p in json_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if data.get("action") == "cli_push" or data.get("source") == "cli":
                return data
        except Exception:
            continue
    return None


def send_post_payload(payload: dict) -> tuple[bool, dict]:
    """Transmit pushing payload to the Cache Vault local bridge."""
    host, port, enabled = load_bridge_config()
    if not enabled:
        return False, {
            "error": "bridge_disabled",
            "message": "Mobile Access (LAN Bridge) is disabled in settings.",
        }

    try:
        device_id, token = get_auth_token_or_pair()
    except Exception as e:
        return False, {
            "error": "pairing_failed",
            "message": f"Could not establish pairing token: {e}",
        }

    url = f"http://{host}:{port}/mobile/v1/inbox/send"
    headers = {
        "Content-Type": "application/json",
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(
        url,
        headers=headers,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return True, data
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"error": "http_error", "message": str(e)}
        if e.code in (401, 403):
            body["message"] = (
                f"{body.get('message', '')} Repair hint: Your CLI token may have been "
                "revoked or desynchronized. Run 'cv reset-auth' to re-establish pairing."
            )
        return False, body
    except urllib.error.URLError as e:
        return False, {
            "error": "unreachable",
            "message": f"Local bridge at {host}:{port} is unreachable. Ensure desktop app is running. Details: {e.reason}",
        }


def run_push(args: argparse.Namespace) -> None:
    content = args.content
    if not content:
        if not sys.stdin.isatty():
            content = sys.stdin.read().strip()
        else:
            print("Error: No content provided. Specify text as an argument or pipe via stdin.", file=sys.stderr)
            sys.exit(1)

    from cache_vault.core import models
    payload = {
        "item_type": "text",
        "content": content,
        "source_app": "CLI",
        "source_device_name": models.CLI_DEVICE_NAME,
    }
    if args.title:
        payload["title"] = args.title
    if args.safe:
        payload["safe_id"] = args.safe

    ok, res = send_post_payload(payload)
    if ok:
        print("Success: Pushed to Cache Vault.")
        print(f"Clip ID: {res.get('clip_id')}")
        if res.get("warning"):
            print(f"Warning: {res.get('warning')}")
    else:
        print(f"Error: {res.get('error')} - {res.get('message', '')}", file=sys.stderr)
        sys.exit(1)


def run_push_url(args: argparse.Namespace) -> None:
    from cache_vault.core import models
    payload = {
        "item_type": "url",
        "content": args.url,
        "source_app": "CLI",
        "source_device_name": models.CLI_DEVICE_NAME,
    }
    if args.safe:
        payload["safe_id"] = args.safe

    ok, res = send_post_payload(payload)
    if ok:
        print("Success: Pushed URL to Cache Vault.")
        print(f"Clip ID: {res.get('clip_id')}")
    else:
        print(f"Error: {res.get('error')} - {res.get('message', '')}", file=sys.stderr)
        sys.exit(1)


def run_push_file(args: argparse.Namespace) -> None:
    file_path = Path(args.file_path)
    if not file_path.exists() or not file_path.is_file():
        print(f"Error: File '{file_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    suffix = file_path.suffix.lower()
    is_image = suffix in (".png", ".jpg", ".jpeg", ".webp", ".gif")

    from cache_vault.core import models
    if is_image:
        mime_type = "image/png" if suffix == ".png" else "image/jpeg"
        try:
            file_bytes = file_path.read_bytes()
            content_b64 = base64.b64encode(file_bytes).decode("utf-8")
        except Exception as e:
            print(f"Error reading image file: {e}", file=sys.stderr)
            sys.exit(1)

        payload = {
            "item_type": "image",
            "content_b64": content_b64,
            "mime_type": mime_type,
            "filename": file_path.name,
            "source_app": "CLI",
            "source_device_name": models.CLI_DEVICE_NAME,
        }
    else:
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"Error reading text file: {e}", file=sys.stderr)
            sys.exit(1)

        payload = {
            "item_type": "text",
            "content": content,
            "source_app": "CLI",
            "source_device_name": models.CLI_DEVICE_NAME,
        }

    if args.safe:
        payload["safe_id"] = args.safe

    ok, res = send_post_payload(payload)
    if ok:
        print(f"Success: Pushed file '{file_path.name}' to Cache Vault.")
        print(f"Clip ID: {res.get('clip_id')}")
    else:
        print(f"Error: {res.get('error')} - {res.get('message', '')}", file=sys.stderr)
        sys.exit(1)


def run_doctor() -> None:
    print("=== Cache Vault Developer CLI Doctor ===")
    host, port, enabled = load_bridge_config()
    print(f"Bridge endpoint: http://{host}:{port}")
    print(f"Bridge enabled in settings: {enabled}")

    config_path = Path.home() / ".cache_vault_cli.json"
    print(f"CLI Config path: {config_path}")
    print(f"CLI Config exists: {config_path.exists()}")

    try:
        device_id, token = get_auth_token_or_pair()
        print(f"CLI Device ID: {device_id}")
    except Exception as e:
        print(f"CLI Pairing status: FAILED - {e}")
        sys.exit(1)

    url = f"http://{host}:{port}/mobile/v1/status"
    headers = {
        "X-Device-Id": device_id,
        "Authorization": f"Bearer {token}",
    }

    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=3) as resp:
            status = json.loads(resp.read().decode("utf-8"))
            print("Authorization status: Authorized")
            print(f"Server version: {status.get('version', 'unknown')}")
            print(f"Active devices count: {status.get('paired_count', 0)}")
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            print("Authorization status: UNAUTHORIZED (Bad Token). Repair via 'cv reset-auth'.")
        else:
            print(f"Authorization status: HTTP Error {e.code}")
        sys.exit(1)
    except urllib.error.URLError as e:
        print("Authorization status: Unreachable (Bridge Off)")
        print(f"Reason: {e.reason}")
        print("Hint: Ensure Cache Vault is running and Mobile Access is enabled.")
        sys.exit(1)


def run_receipt(args: argparse.Namespace) -> None:
    if args.target == "latest":
        receipt = get_latest_receipt()
        if not receipt:
            print("No receipts found.")
            sys.exit(1)
        print(json.dumps(receipt, indent=2))


def run_reset_auth() -> None:
    config_path = Path.home() / ".cache_vault_cli.json"

    try:
        from cache_vault.core.settings import Settings
        from cache_vault.core import models
        settings = Settings.load()
        original_count = len(settings.paired_devices)
        settings.paired_devices = [
            d for d in settings.paired_devices
            if d.get("device_id") != models.CLI_DEVICE_ID
        ]
        if len(settings.paired_devices) < original_count:
            settings.save()
            print("CLI paired device successfully removed from Cache Vault settings.")
    except Exception as e:
        print(f"Warning: Could not remove CLI paired device from Cache Vault settings: {e}")

    if config_path.exists():
        try:
            config_path.unlink()
            print(f"CLI configuration file deleted successfully: {config_path}")
        except OSError as e:
            print(f"Error: Could not delete CLI configuration file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"No CLI configuration file found at: {config_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cv",
        description="Cache Vault Developer CLI - Push text, URLs, and files to your local vault.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # push
    push_parser = subparsers.add_parser("push", help="Push text from argument or stdin.")
    push_parser.add_argument("content", nargs="?", help="Text content to push. If omitted, read from stdin.")
    push_parser.add_argument("--title", help="Optional title for the clip.")
    push_parser.add_argument("--safe", help="Target Safe name or ID.")

    # push-url
    url_parser = subparsers.add_parser("push-url", help="Push a URL as a link clip.")
    url_parser.add_argument("url", help="URL to push.")
    url_parser.add_argument("--safe", help="Target Safe name or ID.")

    # push-file
    file_parser = subparsers.add_parser("push-file", help="Push a file (image or text) as a clip.")
    file_parser.add_argument("file_path", help="Path to the file to push.")
    file_parser.add_argument("--safe", help="Target Safe name or ID.")

    # doctor
    subparsers.add_parser("doctor", help="Check local bridge connection and pair status.")

    # receipt
    receipt_parser = subparsers.add_parser("receipt", help="Show CLI receipts.")
    receipt_parser.add_argument("target", choices=["latest"], help="Target receipt (e.g. 'latest').")

    # reset-auth
    subparsers.add_parser(
        "reset-auth",
        aliases=["unpair"],
        help="Delete local CLI config and unpair from Cache Vault.",
    )

    args = parser.parse_args()

    if args.command == "push":
        run_push(args)
    elif args.command == "push-url":
        run_push_url(args)
    elif args.command == "push-file":
        run_push_file(args)
    elif args.command == "doctor":
        run_doctor()
    elif args.command == "receipt":
        run_receipt(args)
    elif args.command in ("reset-auth", "unpair"):
        run_reset_auth()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
