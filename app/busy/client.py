"""Async HTTP client for the "BUSY as Web Service" API.

Ported from ``../Busin/code/busy-probe/src/busyClient.js``. BUSY runs an HTTP
server (default port 981); every call is a GET where ALL parameters —
including the service code and any XML payload — are sent as request
*headers*, not query string or body. The response carries a ``Result``
header (``"T"``/``"F"``), a ``Description`` header (error text when
``Result="F"``), and the data in the response body.

Mostly read-only (SC=1, 8, 9). `add_voucher` (SC=2) is the one write method —
see CLAUDE.md §2.2: every BUSY write goes through the outbox queue
(app/outbox/), never called inline from a request handler. This client
doesn't enforce that itself; only app/outbox/worker.py may call
`add_voucher`. SC=5/6/7 (add/modify master) remain unimplemented — nothing
in this codebase needs them yet.
"""

from dataclasses import dataclass
from types import TracebackType

import httpx

from app.busy.constants import ServiceCode
from app.config import Settings


@dataclass(frozen=True)
class BusyResponse:
    status_code: int
    result: str | None
    description: str | None
    body: str


class BusyError(RuntimeError):
    """Raised when BUSY responds with ``Result != "T"`` for a given operation."""

    def __init__(self, operation: str, response: BusyResponse) -> None:
        message = (
            f"{operation} failed: {response.description or 'unknown error'} "
            f"(Result={response.result or 'none'}, HTTP {response.status_code})"
        )
        super().__init__(message)
        self.operation = operation
        self.response = response


class BusyClient:
    """Thin wrapper around one BUSY company connection. One instance per process is fine —
    BUSY itself is a single instance with no proven write concurrency (CLAUDE.md §8)."""

    def __init__(
        self, *, host: str, port: int, username: str, password: str, timeout_seconds: float = 30.0
    ) -> None:
        self._username = username
        self._password = password
        self._base_url = f"http://{host}:{port}/"
        self._http = httpx.AsyncClient(timeout=timeout_seconds)

    @classmethod
    def from_settings(cls, settings: Settings) -> "BusyClient":
        """Build a client from app config — the normal way to obtain one outside tests."""
        return cls(
            host=settings.busy_host,
            port=settings.busy_port,
            username=settings.busy_username,
            password=settings.busy_password,
            timeout_seconds=settings.busy_timeout_seconds,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "BusyClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def _call(self, extra_headers: dict[str, str]) -> BusyResponse:
        """Add the auth headers required on every call and issue the request."""
        headers = {"UserName": self._username, "Pwd": self._password, **extra_headers}
        response = await self._http.get(self._base_url, headers=headers)
        return BusyResponse(
            status_code=response.status_code,
            result=response.headers.get("Result"),
            description=response.headers.get("Description"),
            body=response.text,
        )

    async def run_query(self, sql: str) -> str:
        """SC=1 — run a read-only SQL query; returns the recordset as an XML string."""
        response = await self._call({"SC": str(ServiceCode.GET_XML_FROM_RECORDSET), "Qry": sql})
        if response.result != "T":
            raise BusyError("Query", response)
        return response.body

    async def get_master_xml(self, master_code: str | int) -> str:
        """SC=9 — full master XML by master code (read-only)."""
        response = await self._call(
            {"SC": str(ServiceCode.GET_MASTER_XML), "MasterCode": str(master_code)}
        )
        if response.result != "T":
            raise BusyError("GetMasterXML", response)
        return response.body

    async def get_voucher_xml(self, vch_code: str | int) -> str:
        """SC=8 — full voucher XML by voucher code (read-only)."""
        response = await self._call(
            {"SC": str(ServiceCode.GET_VOUCHER_XML), "VchCode": str(vch_code)}
        )
        if response.result != "T":
            raise BusyError("GetVchXML", response)
        return response.body

    async def add_voucher(self, vch_type: int, vch_xml: str) -> str:
        """SC=2 — insert a new voucher; returns the new Voucher Code BUSY assigns.

        Only the outbox worker (app/outbox/worker.py) may call this — CLAUDE.md §2.2,
        every BUSY write goes through the queue, no exceptions."""
        response = await self._call(
            {"SC": str(ServiceCode.ADD_VOUCHER), "VchType": str(vch_type), "VchXml": vch_xml}
        )
        if response.result != "T":
            raise BusyError("AddVoucher", response)
        return response.body
