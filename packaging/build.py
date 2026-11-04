"""Ejecutable autocontenido de ZenithStars v2 con PyInstaller.

    pip install pyinstaller            (+ pywin32 en Windows, para ASCOM COM)
    python packaging/build.py          → dist/ZenithStars-<versión>-<so>.zip

Modo carpeta (onedir), no onefile: arranca más rápido y los antivirus de
Windows lo marcan bastante menos que un .exe autoextraíble.
"""
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from zenithstars import __version__  # noqa: E402

DATA = [('catalog_full.json', '.'), ('index.html', '.'), ('zenithstars/web', 'zenithstars/web')]
HIDDEN = ['win32com.client', 'pythoncom', 'pywintypes'] if sys.platform == 'win32' else []


def main():
    args = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir',
            '--name', 'ZenithStars', '--distpath', str(ROOT / 'dist'),
            '--workpath', str(ROOT / 'build'), '--specpath', str(ROOT / 'build')]
    for src, dest in DATA:
        args += ['--add-data', f'{ROOT / src}{os.pathsep}{dest}']
    for h in HIDDEN:
        args += ['--hidden-import', h]
    subprocess.run(args + [str(ROOT / 'packaging' / 'launcher.py')], check=True)

    osname = {'win32': 'windows', 'darwin': 'macos'}.get(sys.platform, sys.platform)
    stem = ROOT / 'dist' / f'ZenithStars-{__version__}-{osname}-{platform.machine().lower()}'
    shutil.copy(ROOT / 'packaging' / 'LEEME.txt', ROOT / 'dist' / 'ZenithStars' / 'LEEME.txt')
    zip_path = shutil.make_archive(str(stem), 'zip', ROOT / 'dist', 'ZenithStars')
    print(f'\n→ {zip_path}')


if __name__ == '__main__':
    main()
