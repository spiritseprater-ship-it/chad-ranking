# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for JARVIS (Windows, onedir).

Run from this folder:

    pyinstaller --noconfirm JARVIS.spec

The build produces ``dist/JARVIS/JARVIS.exe`` plus its runtime folder. Keep the
folder next to the executable - deleting it breaks the app.

Size notes (measured during development, October 2026):

* PySide6 + numpy + the Gemini SDK account for most of the runtime.
* onnxruntime + scipy + scikit-learn are bundled for the local wake word
  (openwakeword imports all three at import time). They are the largest
  contributors together and cannot be dropped without losing always-on wake
  detection.
* Playwright's Chromium is NOT bundled. Browser automation needs
  ``playwright install chromium`` once on the target PC (~150 MB in the user
  profile), which is why it stays optional and disabled by default.
"""

import os

APP_NAME = "JARVIS"
BASE_DIR = SPECPATH  # directory of this spec file

datas = []
binaries = []
hiddenimports = []

# keep the asset folder if it exists (icons are generated at runtime)
assets_dir = os.path.join(BASE_DIR, "assets")
if os.path.isdir(assets_dir):
    datas.append((assets_dir, "assets"))

# read-only default config + user manual, copied into the bundle. At first run
# JARVIS copies config.json out of the bundle into the per-user data folder so
# the user never has to write inside the application folder.
for _name in ("config.json", "README.txt"):
    _path = os.path.join(BASE_DIR, _name)
    if os.path.isfile(_path):
        # DEST_DIR "." puts them in the bundle root, where paths.resource_dir()
        # (sys._MEIPASS) finds them. PyInstaller 6 rejects an empty string here.
        datas.append((_path, "."))

# --- modules PyInstaller cannot discover on its own -------------------------
try:
    from PyInstaller.utils.hooks import collect_submodules

    for module in (
        "pywinauto",
        "pycaw",
        "comtypes",
        "speech_recognition",
        "openwakeword",
        "google.genai",
        "pyttsx3",
    ):
        try:
            hiddenimports.extend(collect_submodules(module))
        except Exception:
            pass
except Exception:  # pragma: no cover - hooks unavailable during a dry run
    pass

hiddenimports += [
    "dotenv",
    "sounddevice",
    "pyautogui",
    "PIL",
    "cv2",
]

# --- drop heavy, unused libraries -------------------------------------------
excludes = [
    "tkinter",
    "matplotlib",
    # scipy is deliberately NOT excluded: openwakeword imports it (and
    # scikit-learn) at import time, and the local wake word is a core
    # feature. The size cost is real - see the header note.
    "pandas",
    "IPython",
    "jupyter",
    "notebook",
    "pytest",
    "setuptools",
    "pip",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtMultimedia",
]

a = Analysis(
    [os.path.join(BASE_DIR, "main.py")],
    pathex=[BASE_DIR],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    # NOTE: PyInstaller 6 removed the `cipher` and `win_no_prefer_redirects`
    # arguments (and there is nothing to encrypt for a local desktop app), so
    # this spec targets PyInstaller 6.x - see pyinstaller>=6.3.0 in requirements.txt.
    win_private_assemblies=False,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no console window on double-click
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,             # icon is drawn at runtime; add one here if you have it
    version=None,
)
