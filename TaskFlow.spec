# -*- mode: python ; coding: utf-8 -*-

# Keep the small release footprint when the previous local TaskFlow build is
# available. It contains the same Qt runtime ABI; this only swaps a runtime
# DLL selected by PyInstaller, without changing application code or visuals.
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

_root = Path(SPECPATH)
_legacy_exe = _root / 'build' / 'release_backup_20260913_232339' / 'TaskFlow.previous.exe'
_legacy_names = ['libcrypto-3-x64.dll', 'libpng16.dll', 'liblzma.dll', 'LIBBZ2.dll']
_legacy_files = {name: _root / 'build' / ('legacy_' + name) for name in _legacy_names}
if _legacy_exe.exists():
    _legacy_reader = CArchiveReader(str(_legacy_exe))
    for _name, _path in _legacy_files.items():
        if not _path.exists():
            _path.write_bytes(_legacy_reader.extract(_name))
_removed_compat_api = {
    'api-ms-win-core-fibers-l1-1-0.dll',
    'api-ms-win-core-fibers-l1-1-1.dll',
    'api-ms-win-core-kernel32-legacy-l1-1-1.dll',
    'api-ms-win-core-sysinfo-l1-2-0.dll',
}


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources', 'resources')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
if _legacy_exe.exists():
    a.binaries = type(a.binaries)([
        entry for entry in a.binaries
        if entry[0] not in _legacy_names and entry[0] not in _removed_compat_api
    ])
    for _name, _path in _legacy_files.items():
        a.binaries.append((_name, str(_path), 'BINARY'))
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='TaskFlow',
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
    icon=['resources/icon.ico'],
)
