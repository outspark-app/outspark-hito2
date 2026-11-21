#!/usr/bin/env python3
"""Serve the compiled Flutter app at /app/ on the documented loopback port."""
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]/'dist/client'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path == '/':
            self.send_response(302)
            self.send_header('Location', '/app/')
            self.end_headers()
            return
        if not parsed.path.startswith('/app/'):
            self.send_error(404)
            return
        relative = unquote(parsed.path[len('/app/'):])
        candidate = (ROOT/relative).resolve()
        if not candidate.is_relative_to(ROOT.resolve()):
            self.send_error(404)
            return
        self.path = '/'+relative
        if not candidate.exists() and '.' not in Path(relative).name:
            self.path = '/index.html'
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    if not (ROOT/'index.html').exists():
        raise SystemExit('Falta la compilación: ejecuta scripts/flutter_project.py build.')
    print('Outspark Flutter: http://127.0.0.1:5178/app/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', 5178), Handler).serve_forever()
