"""Export the Cache Vault icon to PNG + multi-size ICO from the shared renderer.

    python tools/make_icon.py

Writes assets/icon.png (256px) and assets/icon.ico (16–256px). Run after
changing cache_vault/ui/icon.py so the packaged exe / window / tray icons and
the committed asset stay in sync.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cache_vault.ui.icon import render_icon

ASSETS = Path(__file__).resolve().parent.parent / "assets"


_SIZES = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def _export(stem: str, cash: bool) -> None:
    img = render_icon(256, cash=cash)
    png = ASSETS / f"{stem}.png"
    ico = ASSETS / f"{stem}.ico"
    img.save(png)
    img.save(ico, sizes=_SIZES)
    print(f"wrote {png}")
    print(f"wrote {ico}")


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    _export("icon", cash=False)
    _export("icon-cash", cash=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
