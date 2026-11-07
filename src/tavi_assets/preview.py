"""Loopback-only, offline developer storefront; no production authentication."""
import hmac
import json
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .core import AssetError

WEB = Path(__file__).parent / "web"


def create_preview_server(service, port=0):
    token = secrets.token_urlsafe(32)

    class Handler(BaseHTTPRequestHandler):
        server_version = "TaviAssetsPreview/0.1"

        def _host_ok(self):
            host = self.headers.get("Host", "")
            return host == f"127.0.0.1:{self.server.server_port}"

        def _headers(self, status, content_type, length):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if content_type.startswith("image/svg+xml"):
                self.send_header("Content-Security-Policy", "sandbox; default-src 'none'")
            else:
                self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
            self.end_headers()

        def _reply(self, status, body, content_type="application/json; charset=utf-8"):
            if isinstance(body, dict):
                body = json.dumps(body).encode("utf-8")
            self._headers(status, content_type, len(body))
            self.wfile.write(body)

        def _error(self, status, message):
            self._reply(status, {"error": message})

        def do_GET(self):
            if not self._host_ok():
                self._error(403, "invalid preview host")
                return
            url = urlsplit(self.path)
            if url.path in ("/", "/index.html", "/style.css", "/main.js"):
                file = {"/": "index.html", "/index.html": "index.html", "/style.css": "style.css", "/main.js": "main.js"}[url.path]
                mime = {"index.html": "text/html", "style.css": "text/css", "main.js": "application/javascript"}[file]
                self._reply(200, (WEB / file).read_bytes(), mime + "; charset=utf-8")
                return
            if url.path == "/api/state":
                self._reply(200, {"items": service.describe(), "token": token, "mode": "offline-preview", "purchasesEnabled": False})
                return
            if url.path == "/api/metadata":
                q = parse_qs(url.query)
                try:
                    self._reply(200, service.metadata(q.get("id", [""])[0]))
                except AssetError as exc:
                    self._error(400, str(exc))
                return
            if url.path == "/api/preview":
                q = parse_qs(url.query)
                try:
                    data, mime = service.preview(q.get("id", [""])[0], q.get("capability", [""])[0], q.get("variant", [None])[0])
                    self._reply(200, data, mime)
                except AssetError as exc:
                    self._error(400, str(exc))
                return
            self._error(404, "not found")

        def do_POST(self):
            if not self._host_ok() or self.headers.get("Origin") not in (None, f"http://127.0.0.1:{self.server.server_port}"):
                self._error(403, "wrong origin")
                return
            if not hmac.compare_digest(self.headers.get("X-Tavi-Preview-Token", ""), token):
                self._error(403, "preview token required")
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self._error(415, "JSON required")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("bad length")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("bad body")
                path = urlsplit(self.path).path
                if path == "/api/install":
                    service.install("local-preview", body.get("id"))
                elif path == "/api/select":
                    service.select(body.get("id"), body.get("capability"), body.get("variant"))
                elif path == "/api/uninstall":
                    service.uninstall(body.get("id"))
                else:
                    self._error(404, "unknown operation")
                    return
                self._reply(200, {"ok": True, "items": service.describe()})
            except (ValueError, TypeError, AssetError) as exc:
                self._error(400, str(exc))

        def log_message(self, format, *args):
            pass  # Do not emit browser request URLs/tokens to logs.

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run_preview(service, port=8765, launch=False):
    from webbrowser import open as open_browser
    server = create_preview_server(service, port)
    url = f"http://127.0.0.1:{server.server_port}/"
    print(f"Tavi Assets local storefront: {url}\nCtrl+C to stop. No purchases or internet access.", flush=True)
    if launch:
        open_browser(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
