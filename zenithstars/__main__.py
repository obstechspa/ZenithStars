"""python -m zenithstars [--port 8001] [--min-alt 30] [--no-browser]"""
import argparse
import sys

from . import __version__
from .app import serve


def main():
    # consolas de Windows en cp1252/cp850: un carácter fuera de la tabla no debe tumbar el servidor
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='replace')
    p = argparse.ArgumentParser(prog='zenithstars', description=f'ZenithStars {__version__}')
    p.add_argument('--host', default='127.0.0.1', help='interfaz de escucha (default: solo este PC)')
    p.add_argument('--port', type=int, default=8001, help='puerto HTTP (default 8001; v1 usa 8000)')
    p.add_argument('--min-alt', type=float, default=30.0, help='altura mínima para slew [deg]')
    p.add_argument('--no-browser', action='store_true', help='no abrir el navegador')
    a = p.parse_args()
    serve(a.host, a.port, a.min_alt, open_browser=not a.no_browser)


if __name__ == '__main__':
    main()
