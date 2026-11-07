import json
import tempfile
import threading
import unittest
from http.client import HTTPConnection
from pathlib import Path

from tavi_assets.catalog import Catalog, StoreService
from tavi_assets.core import AssetManager
from tavi_assets.preview import create_preview_server

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"
ID = "org.tavi.cards.standard"


class TestPreview(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.server = create_preview_server(StoreService(AssetManager(self.tmp.name), Catalog(EXAMPLES)))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=4)
        self.tmp.cleanup()

    def request(self, method, path, body=None, headers=None):
        c = HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        c.request(method, path, json.dumps(body) if body is not None else None, headers or {})
        r = c.getresponse(); data = r.read(); status = r.status; meta = dict(r.getheaders()); c.close()
        return status, data, meta

    def test_ui_loaded_and_catalog_state(self):
        status, html, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"One place for your", html)
        status, css, _ = self.request("GET", "/style.css")
        self.assertEqual(status, 200)
        self.assertIn(b".hero", css)
        status, js, _ = self.request("GET", "/main.js")
        self.assertEqual(status, 200)
        self.assertIn(b"/api/install", js)
        status, data, headers = self.request("GET", "/api/state")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["items"][0]["id"], ID)
        self.assertFalse(json.loads(data)["purchasesEnabled"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_post_requires_csrf_token(self):
        headers = {"Content-Type": "application/json"}
        s, _, _ = self.request("POST", "/api/install", {"id": ID}, headers)
        self.assertEqual(s, 403)
        _, data, _ = self.request("GET", "/api/state")
        token = json.loads(data)["token"]
        headers["X-Tavi-Preview-Token"] = token
        headers["Origin"] = "https://attacker.invalid"
        s, _, _ = self.request("POST", "/api/install", {"id": ID}, headers)
        self.assertEqual(s, 403)
        headers.pop("Origin")
        s, _, _ = self.request("POST", "/api/install", {"id": ID}, headers)
        self.assertEqual(s, 200)
        s, data, _ = self.request("GET", "/api/state")
        self.assertEqual(json.loads(data)["items"][0]["installed"], "0.1.2")
        s, _, _ = self.request("POST", "/api/select", {"id": ID, "capability": "card.back", "variant": "blue"}, headers)
        self.assertEqual(s, 200)
        s, data, _ = self.request("GET", "/api/state")
        self.assertEqual(json.loads(data)["items"][0]["preferences"]["card.back"], "blue")
        s, _, _ = self.request("POST", "/api/uninstall", {"id": ID}, headers)
        self.assertEqual(s, 200)
        s, data, _ = self.request("GET", "/api/state")
        self.assertIsNone(json.loads(data)["items"][0]["installed"])

    def test_host_header_is_rejected(self):
        s, _, _ = self.request("GET", "/api/state", headers={"Host": "attacker.invalid"})
        self.assertEqual(s, 403)

    def test_preview_is_verified_image_and_no_active_scripts(self):
        s, data, headers = self.request("GET", f"/api/preview?id={ID}&capability=card.back&variant=blue")
        self.assertEqual(s, 200)
        self.assertIn(b"3455aa", data)
        self.assertEqual(headers["Content-Type"], "image/svg+xml")
        self.assertIn("sandbox", headers["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
