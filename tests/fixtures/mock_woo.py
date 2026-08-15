"""Fake WooCommerce REST API v3 — for testing app/integrations/woocommerce.py without a
real site. Ported from ``../Busin/code/busy-probe/src/mock-woo.js``.

State lives on the server instance (not module globals) so each `run_mock_woo_server()`
call — one per test, via the `mock_woo_server` fixture — starts with a clean, isolated
in-memory catalog.
"""

import json
import re
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread
from typing import Any
from urllib.parse import parse_qs, urlparse

JsonDict = dict[str, Any]

_PRODUCT_ID_RE = re.compile(r"^/wp-json/wc/v3/products/(\d+)$")


class MockWooServer(ThreadingHTTPServer):
    """Adds the in-memory product/category store the handler mutates."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.lock = Lock()
        self.next_product_id = 1000
        self.next_category_id = 500
        self.categories: list[JsonDict] = []
        self.products: list[JsonDict] = []


class MockWooHandler(BaseHTTPRequestHandler):
    server: MockWooServer  # narrows the inherited handler's `server` attribute

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass  # keep test output quiet; failures still surface via assertions

    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> JsonDict:
        length = int(self.headers.get("Content-Length", 0))
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/wp-json/wc/v3/products/categories":
            search = parse_qs(parsed.query).get("search", [""])[0].lower()
            with self.server.lock:
                matches = [c for c in self.server.categories if search in str(c["name"]).lower()]
            self._send_json(200, matches)
            return
        if parsed.path == "/__dump":
            with self.server.lock:
                self._send_json(
                    200, {"products": self.server.products, "categories": self.server.categories}
                )
            return
        self._send_json(404, {"message": "not found", "path": parsed.path})

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        body = self._read_json_body()
        if parsed.path == "/wp-json/wc/v3/products/categories":
            with self.server.lock:
                category = {"id": self.server.next_category_id, "name": body.get("name", "")}
                self.server.next_category_id += 1
                self.server.categories.append(category)
            self._send_json(201, category)
            return
        if parsed.path == "/wp-json/wc/v3/products":
            with self.server.lock:
                product = {"id": self.server.next_product_id, **body}
                self.server.next_product_id += 1
                self.server.products.append(product)
            self._send_json(201, product)
            return
        self._send_json(404, {"message": "not found", "path": parsed.path})

    def do_PUT(self) -> None:
        parsed = urlparse(self.path)
        match = _PRODUCT_ID_RE.match(parsed.path)
        if not match:
            self._send_json(404, {"message": "not found", "path": parsed.path})
            return
        product_id = int(match.group(1))
        body = self._read_json_body()
        with self.server.lock:
            product = next((p for p in self.server.products if p["id"] == product_id), None)
            if product is None:
                self._send_json(404, {"message": "Product not found"})
                return
            product.update(body)
        self._send_json(200, product)


def server_host_port(server: ThreadingHTTPServer) -> tuple[str, int]:
    """`server_address` is typed loosely for socketserver's AF_UNIX case; this server is
    always AF_INET, so the host is always a str."""
    host, port = server.server_address[:2]
    return str(host), int(port)


@contextmanager
def run_mock_woo_server(host: str = "127.0.0.1", port: int = 0) -> Iterator[MockWooServer]:
    """Start the mock WooCommerce server on a background thread; ``port=0`` picks a free port."""
    server = MockWooServer((host, port), MockWooHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()
