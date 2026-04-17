"""
ZenithStars - servidor local
Ejecutar: python server.py
Luego abrir: http://localhost:8000
"""
import http.server, webbrowser, threading, os

PORT = 8000
os.chdir(os.path.dirname(os.path.abspath(__file__)))

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    def log_message(self, fmt, *args):
        pass  # silenciar logs

def open_browser():
    webbrowser.open(f'http://localhost:{PORT}')

print(f'ZenithStars corriendo en http://localhost:{PORT}')
print('Presiona Ctrl+C para detener.\n')

threading.Timer(1.0, open_browser).start()
http.server.HTTPServer(('', PORT), Handler).serve_forever()
