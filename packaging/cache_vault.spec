# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a one-file, windowed Cache Vault build.

Build from the repo root:
    pyinstaller packaging/cache_vault.spec --noconfirm

CustomTkinter ships its themes/assets as data files that must be bundled, so
we collect them (plus pystray's Win32 backend) explicitly.
"""

import os
import sys

from PyInstaller.utils.hooks import collect_all
from PyInstaller.utils.win32.versioninfo import (
    FixedFileInfo,
    StringFileInfo,
    StringStruct,
    StringTable,
    VSVersionInfo,
    VarFileInfo,
    VarStruct,
)

# SPECPATH is the directory containing this spec (…/packaging); the repo root
# is its parent. Using it keeps the build working regardless of the CWD.
ROOT = os.path.dirname(SPECPATH)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from cache_vault.build_meta import windows_version_strings, windows_version_tuple

datas, binaries, hiddenimports = [], [], []
for pkg in ("customtkinter", "zeroconf"):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += [
    "pystray._win32",
    "PIL",
    "PIL.Image",
    "PIL.ImageDraw",
    "cache_vault.core.image_assets",
    "cache_vault.core.mobile.bridge",
    "cache_vault.core.mobile.api",
    "cache_vault.core.mobile.discovery",
    "cache_vault.core.mobile.receipts",
    "cache_vault.core.mobile.models",
    "cache_vault.ui.mobile_dialogs",
]

_icon = os.path.join(ROOT, "assets", "cache-vault-icon.ico")
_version_tuple = windows_version_tuple()
_version_strings = windows_version_strings()
_version_info = VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=_version_tuple,
        prodvers=_version_tuple,
        mask=0x3F,
        flags=0x0,
        OS=0x40004,
        fileType=0x1,
        subtype=0x0,
        date=(0, 0),
    ),
    kids=[
        StringFileInfo([
            StringTable(
                "040904B0",
                [StringStruct(key, value) for key, value in _version_strings.items()],
            )
        ]),
        VarFileInfo([VarStruct("Translation", [1033, 1200])]),
    ],
)
datas += [
    (_icon, "assets"),
    (os.path.join(ROOT, "assets", "cache-vault-icon-256.png"), "assets"),
    (
        os.path.join(ROOT, "cache_vault", "ui", "themes", "proof_foundry.json"),
        os.path.join("cache_vault", "ui", "themes"),
    ),
]

a = Analysis(
    [os.path.join(ROOT, "app.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="CacheVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,       # windowed app, no console
    disable_windowed_traceback=False,
    target_arch=None,
    version=_version_info,
    icon=_icon,
)
