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

    def test_defences(self):
        self.assertEqual(self.req('/api/status', headers={'Host': 'evil.example'})[0], 403)
        self.assertEqual(self.req('/api/slew', b'index=1', ctype='application/x-www-form-urlencoded')[0], 415)
        self.assertEqual(self.req('/api/slew', {'index': 1})[0], 409)          # sin montura
        self.assertEqual(self.req('/api/candidates?alt=95&lat=0&lon=0')[0], 400)


if __name__ == '__main__':
    unittest.main()
