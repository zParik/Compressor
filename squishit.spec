# -*- mode: python ; coding: utf-8 -*-
import platform

block_cipher = None

_sys = platform.system()
if _sys == 'Windows':
    _ffmpeg_bins = [('ffmpeg/ffmpeg.exe', 'ffmpeg'), ('ffmpeg/ffprobe.exe', 'ffmpeg')]
else:
    _ffmpeg_bins = [('ffmpeg/ffmpeg', 'ffmpeg'), ('ffmpeg/ffprobe', 'ffmpeg')]

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=_ffmpeg_bins,
    datas=[('static', 'static')],
    hiddenimports=['flask', 'werkzeug', 'jinja2', 'click', 'itsdangerous'],
    hookspath=[],
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='SquishIt',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,   # Keep console so users can see progress/errors
    icon=None,
)
