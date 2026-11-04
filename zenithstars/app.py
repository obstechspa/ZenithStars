"""Servidor local de ZenithStars v2: UI + API + montura.

Escucha solo en 127.0.0.1 por defecto. Como la API mueve un telescopio, cada
pedido se valida contra el Host (evita DNS rebinding) y los POST exigen
Content-Type JSON (un sitio web cualquiera abierto en el mismo PC no puede
mandar ese tipo sin un preflight CORS, que este servidor no responde).

También sirve la v1 intacta en /v1/ (index.html y catalog_full.json de la raíz).
"""
from __future__ import annotations

import json
import mimetypes
import re
import sys
import threading
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import __version__, astro
from .catalog import Catalog
from .mount import AlpacaMount, ComMount, MountError, com_available, discover_alpaca


def resource_root() -> Path:
    """Raíz del repo, o la carpeta temporal de PyInstaller si es un ejecutable."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


ROOT = resource_root()
WEB = ROOT / 'zenithstars' / 'web'
V1_FILES = {'': 'index.html', 'index.html': 'index.html', 'catalog_full.json': 'catalog_full.json'}


class State:
    def __init__(self, catalog: Catalog, min_alt: float):
        self.catalog = catalog
        self.min_alt = min_alt             # altura mínima para slew [deg]
        self.mount = None
        self.lock = threading.Lock()

    def site(self, q: dict) -> tuple[float, float, str]:
        """(lat, lon) de la montura si está conectada; si no, la que mande la UI."""
        if self.mount is not None:
            try:
                return float(self.mount.get('SiteLatitude')), float(self.mount.get('SiteLongitude')), 'montura'
            except (MountError, TypeError, ValueError):
                pass
        try:
            return float(q['lat']), float(q['lon']), 'manual'
        except (KeyError, ValueError):
            raise ApiError(400, 'Sin montura conectada: indicar latitud y longitud.')


class ApiError(Exception):
    def __init__(self, code: int, msg: str):
        super().__init__(msg)
        self.code = code


def _num(q: dict, key: str, default=None, lo=None, hi=None) -> float:
    raw = q.get(key, default)
    if raw is None or raw == '':
        raise ApiError(400, f'Falta el parámetro {key}.')
    try:
        v = float(raw)
    except (TypeError, ValueError):
        raise ApiError(400, f'{key}={raw!r} no es un número.')
    if (lo is not None and v < lo) or (hi is not None and v > hi):
        raise ApiError(400, f'{key}={v} fuera de rango [{lo}, {hi}].')
    return v


def _parse_utc(v) -> datetime | None:
    """UTCDate de ASCOM ('2026-11-04T16:48:22.9737590Z' o isoformat de COM) → datetime UTC."""
    m = re.match(r'(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(\.\d+)?', str(v or ''))
    if not m:
        return None
    frac = (m.group(2) or '.0')[:7]          # fromisoformat acepta hasta 6 decimales
    return datetime.fromisoformat(m.group(1) + frac).replace(tzinfo=timezone.utc)


def make_handler(state: State, allowed_hosts: set[str]):

    class Handler(BaseHTTPRequestHandler):
        server_version = f'ZenithStars/{__version__}'

        def log_message(self, fmt, *args):
            pass

        # ── plumbing ────────────────────────────────────────────────────
        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

        def _file(self, path: Path):
            if not path.is_file():
                return self._json({'error': 'no encontrado'}, 404)
            ctype = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
            if ctype.startswith('text/') or ctype.endswith('javascript'):
                ctype += '; charset=utf-8'
            self._send(200, path.read_bytes(), ctype)

        def _host_ok(self) -> bool:
            return self.headers.get('Host', '') in allowed_hosts

        def _body(self) -> dict:
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                raise ApiError(415, 'Se espera Content-Type: application/json.')
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n) or b'{}')

        def _dispatch(self, routes: dict, arg):
            if not self._host_ok():
                return self._json({'error': 'Host no permitido'}, 403)
            url = urlparse(self.path)
            fn = routes.get(url.path)
            try:
                if fn is None:
                    return self._static(url.path) if routes is GET else self._json({'error': 'no encontrado'}, 404)
                self._json(fn(arg(url)))
            except ApiError as e:
                self._json({'error': str(e)}, e.code)
            except MountError as e:
                self._json({'error': str(e)}, 502)
            except Exception as e:
                traceback.print_exc()
                self._json({'error': f'{type(e).__name__}: {e}'}, 500)

        def _static(self, path: str):
            if path.startswith('/v1/') or path == '/v1':
                name = V1_FILES.get(path[4:].lstrip('/'))
                return self._file(ROOT / name) if name else self._json({'error': 'no encontrado'}, 404)
            name = path.lstrip('/') or 'index.html'
            target = (WEB / name).resolve()
            if WEB.resolve() not in target.parents:
                return self._json({'error': 'no encontrado'}, 404)
            self._file(target)

        def do_GET(self):
            self._dispatch(GET, lambda u: {k: v[0] for k, v in parse_qs(u.query).items()})

        def do_POST(self):
            self._dispatch(POST, lambda u: self._body())

    # ── API ─────────────────────────────────────────────────────────────
    def api_status(q):
        m = state.mount
        out = {'version': __version__, 'catalog_size': len(state.catalog),
               'min_alt': state.min_alt, 'com_available': com_available(),
               'utc': astro.utcnow().isoformat(), 'mount': None}
        if m is not None:
            st = m.status()
            st['EquatorialSystemName'] = astro.EQ_SYSTEMS.get(st.get('EquatorialSystem'), '?')
            mt = _parse_utc(st.get('UTCDate'))
            st['clock_offset_s'] = None if mt is None else round((mt - astro.utcnow()).total_seconds(), 1)
            out['mount'] = st
        return out

    def api_discover(q):
        return {'alpaca': discover_alpaca(), 'com_available': com_available()}

    def api_candidates(q):
        lat, lon, src = state.site(q)
        t = astro.utcnow()
        mag_min, mag_max = _num(q, 'mag_min', 5), _num(q, 'mag_max', 9)
        if mag_min > mag_max:
            raise ApiError(400, f'V mín ({mag_min:g}) es mayor que V máx ({mag_max:g}).')
        common = dict(lat=lat, lon=lon, t=t, mag_min=mag_min, mag_max=mag_max,
                      min_alt=state.min_alt,
                      iso_arcmin=_num(q, 'iso_arcmin', 3, 0, 59),
                      iso_dmag=_num(q, 'iso_dmag', 2, 0, 10))
        mode = q.get('mode', 'direction')
        extra = {'mode': mode}
        if mode == 'band':
            alt_min, alt_max = _num(q, 'alt_min', 70, 0, 90), _num(q, 'alt_max', 85, 0, 90)
            if alt_min > alt_max:
                raise ApiError(400, f'Altura mín ({alt_min:g}°) es mayor que la máx ({alt_max:g}°).')
            alt_pref = min(max(_num(q, 'alt_pref', (alt_min + alt_max) / 2, 0, 90), alt_min), alt_max)
            az_mode = q.get('az_mode', 'mount')
            az_ref = None
            if az_mode == 'fixed':
                az_ref = _num(q, 'az', 0) % 360
            elif az_mode == 'mount' and state.mount is not None:
                try:
                    az_ref = float(state.mount.get('Azimuth')) % 360
                except (MountError, TypeError, ValueError):
                    az_ref = None          # sin azimut de la montura: se ordena solo por altura
            elif az_mode not in ('mount', 'any'):
                raise ApiError(400, f'az_mode={az_mode!r}: usar "mount", "fixed" o "any".')
            res = state.catalog.band_candidates(alt_min=alt_min, alt_max=alt_max, alt_pref=alt_pref,
                                                az_ref=az_ref, **common)
            extra.update(alt_min=alt_min, alt_max=alt_max, alt_pref=alt_pref, az_ref=az_ref,
                         az_mode=az_mode)
        elif mode == 'direction':
            res = state.catalog.candidates(alt=_num(q, 'alt', 90, 0, 90), az=_num(q, 'az', 0) % 360,
                                           radius=_num(q, 'radius', 15, 0.1, 90), **common)
        else:
            raise ApiError(400, f'mode={mode!r}: usar "band" o "direction".')
        res.update(lat=lat, lon=lon, site_source=src, utc=t.isoformat(), min_alt=state.min_alt, **extra)
        return res

    def api_connect(b):
        with state.lock:
            if state.mount is not None:
                state.mount.disconnect()
                state.mount = None
            kind = b.get('kind')
            if kind == 'alpaca':
                m = AlpacaMount(str(b['url']), int(b.get('device', 0)))
            elif kind == 'com':
                if not com_available():
                    raise ApiError(400, 'COM no disponible: requiere Windows con ASCOM Platform.')
                progid = b.get('progid') or ComMount.choose(b.get('last', ''))
                if not progid:
                    raise ApiError(400, 'No se eligió ningún driver en el ASCOM Chooser.')
                m = ComMount(progid)
            else:
                raise ApiError(400, f'kind={kind!r}: usar "alpaca" o "com".')
            m.connect()
            state.mount = m
            return {'ok': True, 'label': m.label, 'we_connected': m.we_connected,
                    'progid': getattr(m, 'progid', None)}

    def api_disconnect(b):
        with state.lock:
            if state.mount is not None:
                state.mount.disconnect()
            state.mount = None
        return {'ok': True}

    def api_slew(b):
        m = state.mount
        if m is None:
            raise ApiError(409, 'No hay montura conectada.')
        i = int(b['index'])
        if not 0 <= i < len(state.catalog):
            raise ApiError(400, f'index={i} fuera del catálogo.')
        s = state.catalog.stars[i]
        lat, lon, _ = state.site({})
        t = astro.utcnow()
        # se recalcula ahora: la lista en pantalla puede tener minutos
        ra_d, dec_d = astro.precess(s[0], s[1], astro.julian_date(t))
        alt, az = astro.altaz(astro.lst(t, lon) - ra_d, dec_d, lat)
        if alt < state.min_alt:
            raise ApiError(409, f'{s[3] or s[4]} está a {alt:.1f}° de altura, bajo el límite de '
                                f'{state.min_alt:.0f}°.')
        eq = m.get('EquatorialSystem')
        ra_m, dec_m = astro.to_mount_system(s[0], s[1], eq, t)
        notes = m.slew(ra_m / 15.0, dec_m)
        return {'ok': True, 'ra_hours': ra_m / 15.0, 'dec': dec_m, 'alt': alt, 'az': az,
                'eq_system': astro.EQ_SYSTEMS.get(eq, str(eq)), 'notes': notes,
                'seq': (m.arrival or {}).get('seq')}

    def api_abort(b):
        if state.mount is None:
            raise ApiError(409, 'No hay montura conectada.')
        state.mount.abort()
        return {'ok': True}

    GET = {'/api/status': api_status, '/api/discover': api_discover,
           '/api/candidates': api_candidates}
    POST = {'/api/connect': api_connect, '/api/disconnect': api_disconnect,
            '/api/slew': api_slew, '/api/abort': api_abort}
    return Handler


def serve(host: str, port: int, min_alt: float, open_browser: bool = True):
    catalog = Catalog.from_json(ROOT / 'catalog_full.json')
    state = State(catalog, min_alt)
    names = {host, 'localhost', '127.0.0.1'}
    allowed = {f'{h}:{port}' for h in names} | (names if port == 80 else set())
    httpd = ThreadingHTTPServer((host, port), make_handler(state, allowed))
    url = f'http://{"localhost" if host in ("127.0.0.1", "0.0.0.0") else host}:{port}'
    print(f'ZenithStars {__version__} en {url}  (v1 en {url}/v1/)', flush=True)
    print(f'{len(catalog):,} estrellas · altura mínima para slew {min_alt:.0f}° · Ctrl+C para salir', flush=True)
    if open_browser:
        import webbrowser
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if state.mount is not None:
            state.mount.disconnect()
        httpd.server_close()
