"""App proof receipt export — proves edition, features, and build truth."""

from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .. import __copyright__, __description__, __product__, __version__, brand
from ..core.settings import default_settings_path
from ..core.storage import default_db_path
from ..feature_gate import FEATURE_LABELS
from .. import licensing

KNOWN_LIMITATIONS = (
    "Local-first clipboard vault — no cloud sync in this build.",
    "No mobile bridge claim in Founder MVP SKU.",
    "Safes organize clips locally; they are not encryption.",
    "Vault Lock is a UI privacy lock, not file encryption.",
    "Founder features require a valid offline license.",
    "No in-app payment or account system.",
)

NOT_CLAIMED = (
    "Cloud sync",
    "AI-powered organization",
    "Encrypted safes",
    "Team collaboration",
    "Automatic backup",
    "Mobile access (not marketed in Founder MVP)",
    "Military-grade or bank-grade encryption",
)


def _git_commit() -> str:
    try:
        root = Path(__file__).resolve().parents[2]
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _enabled_features() -> list[str]:
    status = licensing.load_license()
    if status.state == licensing.LicenseState.FOUNDER_VALID:
        return sorted(status.features)
    return []


def _disabled_features() -> list[str]:
    enabled = set(_enabled_features())
    return sorted(k for k in FEATURE_LABELS if k not in enabled)


def export_app_receipt(dest_parent: Path) -> Path:
    """Write proof receipt folder under *dest_parent*; return folder path."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M%S")
    folder = dest_parent / f"CacheVault_Proof_{stamp}"
    folder.mkdir(parents=True, exist_ok=True)

    status = licensing.load_license()
    edition = "Founder" if status.state == licensing.LicenseState.FOUNDER_VALID else "Free"
    enabled = _enabled_features()
    disabled = _disabled_features()

    version_path = folder / "VERSION.txt"
    version_path.write_text(f"{__version__}\n", encoding="utf-8")

    license_status_path = folder / "LICENSE_STATUS.txt"
    license_status_path.write_text(
        f"state={status.state.value}\n"
        f"edition={edition}\n"
        f"licensee={status.licensee or ''}\n"
        f"message={status.message}\n",
        encoding="utf-8",
    )

    matrix_path = folder / "FEATURE_MATRIX.md"
    matrix_lines = [
        "# Cache Vault feature matrix (this install)\n",
        f"Edition: **{edition}**\n",
        f"Version: `{__version__}`\n\n",
        "## Enabled Founder features\n",
    ]
    if enabled:
        matrix_lines.extend(f"- `{k}` — {FEATURE_LABELS.get(k, k)}\n" for k in enabled)
    else:
        matrix_lines.append("- *(none — Free edition)*\n")
    matrix_lines.append("\n## Disabled Founder features\n")
    matrix_lines.extend(f"- `{k}` — {FEATURE_LABELS.get(k, k)}\n" for k in disabled)
    matrix_path.write_text("".join(matrix_lines), encoding="utf-8")

    receipt_path = folder / "APP_RECEIPT.md"
    build_date = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    receipt_path.write_text(
        f"# Cache Vault App Proof Receipt\n\n"
        f"| Field | Value |\n|---|---|\n"
        f"| App name | {__product__} |\n"
        f"| Version | `{__version__}` |\n"
        f"| Edition | {edition} |\n"
        f"| Studio | {brand.STUDIO_NAME} |\n"
        f"| Tagline | {brand.STUDIO_TAGLINE} |\n"
        f"| Build date | {build_date} |\n"
        f"| Commit | `{_git_commit()}` |\n"
        f"| License state | {status.state.value} |\n"
        f"| Licensee | {status.licensee or '—'} |\n"
        f"| Python | `{sys.version.split()[0]}` |\n"
        f"| Platform | `{platform.platform()}` |\n"
        f"| Settings path | `{default_settings_path()}` |\n"
        f"| Database path | `{default_db_path()}` |\n"
        f"| Copyright | {__copyright__} |\n\n"
        f"## Description\n\n{__description__}\n\n"
        f"## Enabled features\n\n"
        + ("\n".join(f"- `{k}`" for k in enabled) if enabled else "- Core Free features only")
        + f"\n\n## Disabled Founder features\n\n"
        + "\n".join(f"- `{k}`" for k in disabled)
        + f"\n\n## Known limitations\n\n"
        + "\n".join(f"- {line}" for line in KNOWN_LIMITATIONS)
        + f"\n\n## Not claimed\n\n"
        + "\n".join(f"- {item}" for item in NOT_CLAIMED)
        + f"\n\n## Local-first doctrine\n\n"
        f"No cloud sync. No telemetry. No accounts.\n",
        encoding="utf-8",
    )

    sums: dict[str, str] = {}
    for path in sorted(folder.iterdir()):
        if path.name == "SHA256SUMS.txt":
            continue
        if path.is_file():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            sums[path.name] = digest

    sums_path = folder / "SHA256SUMS.txt"
    sums_path.write_text(
        "\n".join(f"{h}  {name}" for name, h in sorted(sums.items())) + "\n",
        encoding="ascii",
    )

    return folder
