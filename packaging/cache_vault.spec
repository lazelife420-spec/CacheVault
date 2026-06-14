# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for a one-file, windowed Cache Vault build.

Build from the repo root:
    pyinstaller packaging/cache_vault.spec --noconfirm

CustomTkinter ships its themes/assets as data files that must be bundled, so
we collect them (plus pystray's Win32 backend) explicitly.
"""

import os

from PyInstaller.utils.hooks import collect_all

# SPECPATH is the directory containing this spec (…/packaging); the repo root
# is its parent. Using it keeps the build working regardless of the CWD.
ROOT = os.path.dirname(SPECPATH)

datas, binaries, hiddenimports = [], [], []
for pkg in ("customtkinter",):
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

hiddenimports += ["pystray._win32", "PIL", "PIL.Image", "PIL.ImageDraw"]

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
)
