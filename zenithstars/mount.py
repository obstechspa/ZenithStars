"""Monturas ASCOM: Alpaca (HTTP, cualquier SO) y COM (Windows, ASCOM Platform).

Ambas exponen lo mismo: connect, disconnect, status, slew, abort. Los nombres
de propiedad son los de ASCOM (PascalCase); Alpaca los usa en minúscula en la
URL, COM tal cual.

Reglas de seguridad que viven acá y no en la UI:
- nunca se desestaciona (AtPark → error, lo hace el operador desde su software)
- nunca se apaga Connected si la montura ya estaba conectada al llegar: otro
  programa del cliente (NINA, ACP, PWI…) puede estar usándola
- el tracking se enciende solo como parte de un slew pedido explícitamente,
  porque ASCOM exige Tracking=True para SlewToCoordinates
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

CLIENT_ID = 4217                    # ClientID Alpaca fijo para ZenithStars
STATUS_PROPS = ('Name', 'SiteLatitude', 'SiteLongitude', 'RightAscension',
                'Declination', 'Altitude', 'Azimuth', 'Tracking', 'Slewing',
                'AtPark', 'EquatorialSystem', 'UTCDate')


class MountError(RuntimeError):
    pass


class Mount:
    kind = 'base'

    def __init__(self):
        self.label = ''
        self.we_connected = False
        self._lock = threading.Lock()

    # implementadas por cada backend
    def get(self, prop: str): raise NotImplementedError
    def put(self, prop: str, value): raise NotImplementedError
    def call(self, method: str, *args): raise NotImplementedError

    def connect(self):
        with self._lock:
            if not self.get('Connected'):
                self.put('Connected', True)
                self.we_connected = True

    def disconnect(self):
        with self._lock:
            if self.we_connected:
                self.put('Connected', False)
            self.close()

    def close(self):
        pass

    def status(self) -> dict:
        out = {'kind': self.kind, 'label': self.label, 'we_connected': self.we_connected}
        with self._lock:
            for p in STATUS_PROPS:
                try:
                    out[p] = self.get(p)
                except Exception as e:           # una propiedad no implementada no tumba el resto
                    out[p] = None
                    out.setdefault('errors', {})[p] = str(e)
                    if 'sin respuesta' in str(e):  # caída de red: no esperar un timeout por propiedad
                        out['unreachable'] = True
                        break
        return out

    def slew(self, ra_hours: float, dec_deg: float) -> list[str]:
        """Slew asíncrono a (ra, dec) en el sistema de la montura. Devuelve
        las acciones previas que hizo (p. ej. encender tracking)."""
        notes = []
        with self._lock:
            if self.get('AtPark'):
                raise MountError('La montura está estacionada (AtPark). '
                                 'Desestacionarla desde su software y reintentar.')
            if self.get('Slewing'):                # puede ser un park u otro programa del cliente
                raise MountError('La montura ya se está moviendo. Esperar a que termine o abortar.')
            if not self.get('Tracking'):
                if not self.get('CanSetTracking'):
                    raise MountError('Tracking apagado y la montura no permite encenderlo por ASCOM.')
                self.put('Tracking', True)
                notes.append('tracking encendido')
            if self.get('CanSlewAsync'):
                self.call('SlewToCoordinatesAsync', ra_hours, dec_deg)
            else:
                threading.Thread(target=self._slew_sync, args=(ra_hours, dec_deg),
                                 daemon=True).start()
                notes.append('slew síncrono en segundo plano (la montura no tiene CanSlewAsync)')
        return notes

    def _slew_sync(self, ra_hours, dec_deg):
        try:
            self.call('SlewToCoordinates', ra_hours, dec_deg)
        except Exception as e:
            print(f'[zenithstars] slew síncrono falló: {e}', file=sys.stderr)

    def abort(self):
        self.call('AbortSlew')                   # sin lock: tiene que pasar aunque otro pedido esté en curso


# ── Alpaca ──────────────────────────────────────────────────────────────────

class AlpacaMount(Mount):
    kind = 'alpaca'

    def __init__(self, base_url: str, device: int = 0, timeout: float = 5.0):
        super().__init__()
        self.base = base_url.rstrip('/')
        self.device = int(device)
        self.timeout = timeout
        self._tx = 0
        self.label = f'Alpaca {self.base} · telescopio {self.device}'

    def _request(self, method: str, name: str, params: dict):
        self._tx += 1
        params = {**params, 'ClientID': CLIENT_ID, 'ClientTransactionID': self._tx}
        url = f'{self.base}/api/v1/telescope/{self.device}/{name.lower()}'
        data = None
        if method == 'GET':
            url += '?' + urllib.parse.urlencode(params)
        else:
            data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            raise MountError(f'{name}: HTTP {e.code} {e.read().decode(errors="replace")[:200]}')
        except OSError as e:
            raise MountError(f'{name}: sin respuesta de {self.base} ({e})')
        if body.get('ErrorNumber'):
            raise MountError(f'{name}: {body.get("ErrorMessage")} (ASCOM 0x{body["ErrorNumber"]:X})')
        return body.get('Value')

    def get(self, prop):
        return self._request('GET', prop, {})

    def put(self, prop, value):
        v = ('true' if value else 'false') if isinstance(value, bool) else value
        self._request('PUT', prop, {prop: v})

    def call(self, method, *args):
        names = {'SlewToCoordinatesAsync': ('RightAscension', 'Declination'),
                 'SlewToCoordinates': ('RightAscension', 'Declination')}.get(method, ())
        self._request('PUT', method, dict(zip(names, args)))


def discover_alpaca(timeout: float = 1.5, port: int = 32227) -> list[dict]:
    """Descubrimiento Alpaca por broadcast UDP + lista de telescopios de cada servidor."""
    servers = set()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.settimeout(timeout)
        for addr in ('255.255.255.255', '127.0.0.1'):
            try:
                s.sendto(b'alpacadiscovery1', (addr, port))
            except OSError:
                pass
        try:
            while True:
                data, (host, _) = s.recvfrom(1024)
                try:
                    servers.add((host, int(json.loads(data)['AlpacaPort'])))
                except (ValueError, KeyError):
                    pass
        except socket.timeout:
            pass
    found = []
    for host, p in sorted(servers):
        url = f'http://{host}:{p}'
        try:
            with urllib.request.urlopen(f'{url}/management/v1/configureddevices', timeout=3) as r:
                devices = json.loads(r.read().decode()).get('Value', [])
        except (OSError, ValueError) as e:
            found.append({'url': url, 'device': None, 'name': '', 'error': str(e)})
            continue
        for d in devices:
            if d.get('DeviceType', '').lower() == 'telescope':
                found.append({'url': url, 'device': d['DeviceNumber'], 'name': d.get('DeviceName', '')})
    return found


# ── COM (Windows) ───────────────────────────────────────────────────────────

def com_available() -> bool:
    if sys.platform != 'win32':
        return False
    try:
        import win32com.client  # noqa: F401
        return True
    except ImportError:
        return False


class ComMount(Mount):
    """Driver ASCOM por COM. Los objetos COM son de un solo apartamento, así
    que toda llamada pasa por un único hilo dedicado."""
    kind = 'com'

    def __init__(self, progid: str):
        super().__init__()
        import pythoncom
        self._pool = ThreadPoolExecutor(1, initializer=pythoncom.CoInitialize)
        self.progid = progid

        def dispatch():
            import win32com.client
            return win32com.client.Dispatch(progid)
        self._obj = self._run(dispatch)
        self.label = f'ASCOM COM {progid}'

    def _run(self, fn):
        try:
            return self._pool.submit(fn).result(timeout=60)
        except MountError:
            raise
        except Exception as e:
            raise MountError(str(e))

    def get(self, prop):
        v = self._run(lambda: getattr(self._obj, prop))
        return v.isoformat() if hasattr(v, 'isoformat') else v

    def put(self, prop, value):
        self._run(lambda: setattr(self._obj, prop, value))

    def call(self, method, *args):
        self._run(lambda: getattr(self._obj, method)(*args))

    def close(self):
        self._pool.shutdown(wait=False)

    @staticmethod
    def choose(last: str = '') -> str:
        """Abre el ASCOM Chooser en el escritorio del PC y devuelve el ProgID."""
        def pick():
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            ch = win32com.client.Dispatch('ASCOM.Utilities.Chooser')
            ch.DeviceType = 'Telescope'
            return ch.Choose(last) or ''
        with ThreadPoolExecutor(1) as ex:
            return ex.submit(pick).result()
