"""Async WooCommerce REST API v3 client.

Ported from ``../Busin/code/busy-probe/src/wooClient.js``. Docs:
https://woocommerce.github.io/woocommerce-rest-api-docs/

Auth: a Consumer Key/Secret generated in WooCommerce -> Settings -> Advanced -> REST API.
Give it its own dedicated key (Read/Write on Products) rather than reusing an admin's
(PRD §6/CLAUDE.md — same "dedicated service account" principle as the BUSY connection).
"""

import base64
from types import TracebackType
from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings

JsonDict = dict[str, Any]


class WooCommerceError(RuntimeError):
    def __init__(self, method: str, path: str, status_code: int, message: str) -> None:
        super().__init__(f"WooCommerce {method} {path} failed: HTTP {status_code} {message}")
        self.status_code = status_code


class WooCommerceClient:
    def __init__(
        self,
        *,
        site_url: str,
        consumer_key: str,
        consumer_secret: str,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = site_url.rstrip("/") + "/wp-json/wc/v3"
        token = base64.b64encode(f"{consumer_key}:{consumer_secret}".encode()).decode()
        self._http = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        )

    @classmethod
    def from_settings(cls, settings: Settings) -> "WooCommerceClient":
        return cls(
            site_url=settings.woo_site_url,
            consumer_key=settings.woo_consumer_key,
            consumer_secret=settings.woo_consumer_secret,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "WooCommerceClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _request(self, method: str, path: str, json_body: JsonDict | None = None) -> Any:
        response = await self._http.request(method, f"{self._base_url}{path}", json=json_body)
        if response.status_code >= 400:
            try:
                message = str(response.json().get("message", response.text))
            except ValueError:
                message = response.text
            raise WooCommerceError(method, path, response.status_code, message)
        if not response.content:
            return {}
        return response.json()

    async def create_product(self, data: JsonDict) -> JsonDict:
        result: JsonDict = await self._request("POST", "/products", data)
        return result

    async def update_product(self, product_id: int, data: JsonDict) -> JsonDict:
        result: JsonDict = await self._request("PUT", f"/products/{product_id}", data)
        return result

    async def find_category_by_name(self, name: str) -> JsonDict | None:
        matches = await self._request("GET", f"/products/categories?search={quote(name)}")
        if not isinstance(matches, list):
            raise WooCommerceError(
                "GET", "/products/categories", 200, "unexpected response shape (expected a list)"
            )
        for cat in matches:
            if isinstance(cat, dict) and str(cat.get("name", "")).lower() == name.lower():
                return cat
        return None

    async def create_category(self, name: str) -> JsonDict:
        result: JsonDict = await self._request("POST", "/products/categories", {"name": name})
        return result
