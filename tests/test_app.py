"""Servidor HTTP en un hilo, sin montura: rutas, v1 y las defensas de la API."""
import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from zenithstars.app import State, make_handler
from zenithstars.catalog import Catalog

ROOT = Path(__file__).resolve().parent.parent


class TestApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        state = State(Catalog.from_json(ROOT / 'catalog_full.json'), min_alt=30)
        cls.httpd = ThreadingHTTPServer(('127.0.0.1', 0), None)
        port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass = make_handler(state, {f'127.0.0.1:{port}', f'localhost:{port}'})
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{port}'

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, path, body=None, headers=None, ctype='application/json'):
        data = None if body is None else (json.dumps(body).encode() if ctype == 'application/json' else body)
        h = {**({'Content-Type': ctype} if data else {}), **(headers or {})}
        r = urllib.request.Request(self.base + path, data=data, headers=h)
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_ui_and_v1(self):
        self.assertEqual(self.req('/')[0], 200)
        code, body = self.req('/v1/')
        self.assertEqual(code, 200)
        self.assertIn(b'catalog_full.json', body)
        self.assertEqual(self.req('/v1/catalog_full.json')[0], 200)
        self.assertEqual(self.req('/v1/server.py')[0], 404)

    def test_candidates_need_site_without_mount(self):
        self.assertEqual(self.req('/api/candidates?alt=90&az=0')[0], 400)
        code, body = self.req('/api/candidates?alt=90&az=0&lat=-30.47&lon=-70.76')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['site_source'], 'manual')

    def test_band_mode(self):
        base = '/api/candidates?mode=band&lat=-30.47&lon=-70.76&mag_min=6&mag_max=8'
        code, body = self.req(base + '&alt_min=70&alt_max=85&alt_pref=80&az_mode=any')
        self.assertEqual(code, 200)
        r = json.loads(body)
        self.assertEqual((r['mode'], r['alt_min'], r['alt_max'], r['az_ref']), ('band', 70, 85, None))
        self.assertTrue(all(70 <= s['alt'] <= 85 and 6 <= s['vmag'] <= 8 for s in r['stars']))
        r = json.loads(self.req(base + '&alt_min=70&alt_max=85&alt_pref=80&az_mode=fixed&az=450')[1])
        self.assertEqual(r['az_ref'], 90)
        # sin montura, "cerca de la montura" se ordena solo por altura
        self.assertIsNone(json.loads(self.req(base + '&alt_min=70&alt_max=85&az_mode=mount')[1])['az_ref'])
        # la preferida se acota a la banda
        self.assertEqual(json.loads(self.req(base + '&alt_min=70&alt_max=85&alt_pref=89')[1])['alt_pref'], 85)

    def test_band_mode_rejects_bad_criteria(self):
        base = '/api/candidates?mode=band&lat=-30.47&lon=-70.76'
        self.assertEqual(self.req(base + '&alt_min=85&alt_max=70')[0], 400)
        self.assertEqual(self.req(base + '&mag_min=9&mag_max=6')[0], 400)
        self.assertEqual(self.req(base + '&az_mode=norte')[0], 400)
        self.assertEqual(self.req('/api/candidates?mode=xx&lat=0&lon=0')[0], 400)

    def test_defences(self):
        self.assertEqual(self.req('/api/status', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.req('/api/slew', b'index=1', ctype='application/x-www-form-urlencoded')[0], 415)
        self.assertEqual(self.req('/api/slew', {'index': 1})[0], 409)          # sin montura
        self.assertEqual(self.req('/api/candidates?alt=95&lat=0&lon=0')[0], 400)


if __name__ == '__main__':
    unittest.main()
