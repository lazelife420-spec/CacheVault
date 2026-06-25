"""Mobile Access Receipt log — local proof of every mobile API call."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .. import safe_io
from .models import MobileAccessReceipt


def default_receipts_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    return Path(base) / "CacheVault" / "mobile_access_receipts.json"


class MobileReceiptLog:
    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path or default_receipts_path())

    def record(self, receipt: MobileAccessReceipt) -> None:
        rows = self.list_all()
        rows.append(receipt.to_dict())
        # Keep the most recent 500 receipts.
        if len(rows) > 500:
            rows = rows[-500:]
        safe_io.atomic_write_text(self.path, json.dumps(rows, indent=2))

    def list_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except OSError:
            return []
        except json.JSONDecodeError:
            safe_io.quarantine_corrupt(self.path)
            return []
        return data if isinstance(data, list) else []

    def recent(self, limit: int = 100) -> list[dict]:
        return self.list_all()[-limit:]
