# -*- mode: python ; coding: utf-8 -*-
"""VoiceIME PyInstaller spec — single-file .exe build."""

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['voiceime/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'voiceime',
        'voiceime.config',
        'voiceime.config.defaults',
        'voiceime.config.manager',
        'voiceime.model',
        'voiceime.model.manager',
        'voiceime.model.downloader',
        'voiceime.hotkey',
        'voiceime.hotkey.manager',
        'voiceime.hotkey.hook',
        'voiceime.recorder',
        'voiceime.recorder.device',
        'voiceime.recorder.stream',
        'voiceime.asr',
        'voiceime.asr.engine',
        'voiceime.asr.memory',
        'voiceime.output',
        'voiceime.output.controller',
        'voiceime.output.clipboard',
        'voiceime.output.uia',
        'voiceime.output.keyboard',
        'voiceime.ui',
        'voiceime.ui.tray',
        'voiceime.ui.wizard',
        'voiceime.ui.settings',
        'voiceime.utils',
        'voiceime.utils.paths',
        'voiceime.utils.log',
        'voiceime.utils.single_instance',
        'voiceime.protocols',
        'voiceime.core',
        # CTranslate2 / faster-whisper native deps
        'ctranslate2',
        'faster_whisper',
        # Audio
        'sounddevice',
        '_sounddevice_data',
        # GUI
        'PyQt6',
        'PyQt6.QtWidgets',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        # Tray
        'pystray',
        'PIL',
        'PIL.Image',
        'PIL.ImageDraw',
        # Input / output
        'pynput',
        'pyperclip',
        'pyautogui',
        # Other
        'numpy',
        'huggingface_hub',
        'keyring',
        'json',
        'queue',
        'threading',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'pandas',
        'IPython',
        'notebook',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='VoiceIME',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add .ico file path here when available
)
