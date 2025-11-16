# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_dynamic_libs, copy_metadata
import os

datas = []
binaries = []
hiddenimports = []
datas += copy_metadata('imageio', recursive=True)
datas += copy_metadata('imageio-ffmpeg', recursive=True)
_mode = os.environ.get('FASTCAP_BUILD_MODE', '').lower()
_lite = (_mode == 'lite')
_bins = collect_dynamic_libs('PySide6')
_names_core = ['qt6core.dll', 'qt6gui.dll', 'qt6widgets.dll']
_names_plugins = [
    'plugins\\platforms\\qwindows.dll',
    'plugins\\styles\\qwindowsvistastyle.dll',
    'plugins\\styles\\qfusion.dll',
    'plugins\\imageformats\\qico.dll',
    'plugins\\imageformats\\qjpeg.dll',
    'plugins\\imageformats\\qgif.dll',
    'plugins\\imageformats\\qpng.dll',
]
def _match(path, names):
    p = path.lower().replace('/', '\\')
    return any(n in p for n in names)
binaries += [b for b in _bins if _match(b[0], _names_core) or _match(b[0], _names_plugins)]


a = Analysis(
        ['fastcap.py'],
        pathex=[],
        binaries=binaries,
        datas=datas,
        hiddenimports=hiddenimports,
        hookspath=[],
        hooksconfig={},
        runtime_hooks=[],
        excludes=[
            'cv2',
            '_tkinter',
            'selenium',
            'webdriver_manager',
            'pygetwindow',
            'pynput',
            'PySide6.QtWebEngineCore',
            'PySide6.QtWebEngineWidgets',
            'PySide6.QtWebEngineQuick',
            'PySide6.QtMultimedia',
            'PySide6.QtSql',
            'PySide6.QtPdf',
            'PySide6.QtCharts',
            'PySide6.Qt3DCore',
            'PySide6.Qt3DRender',
            'PySide6.Qt3DInput',
            'PySide6.QtNetwork',
            'PySide6.QtQuick',
        ] + (['sounddevice'] if _lite else []),
        noarchive=False,
        optimize=1,
    )
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='FastCap',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
