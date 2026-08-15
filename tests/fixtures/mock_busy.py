"""Fake BUSY web service for tests — no real BUSY server required.

Ported from ``../Busin/code/busy-probe/src/mock-busy.js``. Mimics BUSY's shape: sets a
``Result`` header ("T"/"F"), a ``Description`` header on failure, and returns an XML
recordset (or nested-element XML) in the body — same as the real `busy_client.py` expects.

Run standalone:  python -m tests.fixtures.mock_busy   (listens on 127.0.0.1:8981)
Or use `run_mock_busy_server()` as a pytest fixture — see tests/busy/conftest.py.
"""

import os
import re
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

DEFAULT_PORT = int(os.environ.get("MOCK_PORT", "8981"))


def _rowset(rows: list[dict[str, str]]) -> str:
    """Wrap rows in the real ADO 'persist XML' rowset shape so xml_util.parse_rowset_xml
    can parse it unmodified — same fixture shape the real BUSY server returns."""
    row_tags = "".join(
        "<z:row " + " ".join(f"{k}='{v}'" for k, v in attrs.items()) + "/>" for attrs in rows
    )
    return (
        "<xml xmlns:rs='urn:schemas-microsoft-com:rowset' xmlns:z='#RowsetSchema'>"
        f"<rs:data>{row_tags}</rs:data></xml>"
    )


class MockBusyHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - stdlib signature
        pass  # keep test output quiet; failures still surface via assertions

    def do_GET(self) -> None:
        headers = {k: v for k, v in self.headers.items()}
        sc = headers.get("SC")
        qry = headers.get("Qry", "")

        # Simulate the auth check BUSY does on every call.
        if not headers.get("UserName") or not headers.get("Pwd"):
            self._respond(result="F", description="Missing UserName/Pwd", body="")
            return

        body = "<Ok/>"
        if sc == "1":
            body = self._handle_query(qry)
        elif sc == "9":
            code = headers.get("MasterCode", "0")
            price = os.environ.get("MOCK_ITEM101_PRICE", "1000") if code == "101" else "1000"
            body = (
                f"<Item><Name>Fake Item {code}</Name><MainUnit>Pcs.</MainUnit>"
                f"<SalePrice>{price}</SalePrice><ParentGroup>General</ParentGroup></Item>"
            )
        elif sc == "8":
            vch_code = headers.get("VchCode", "0")
            body = (
                f"<Sale><VchCode>{vch_code}</VchCode>"
                "<MasterName1>Fake Customer</MasterName1></Sale>"
            )

        self._respond(result="T", description=None, body=body)

    def _handle_query(self, qry: str) -> str:
        if re.search(r"INFORMATION_SCHEMA\.TABLES", qry, re.IGNORECASE):
            return _rowset(
                [{"TABLE_NAME": t} for t in ["Master1", "Master2", "Tran1", "Tran2", "Company"]]
            )
        if re.search(r"INFORMATION_SCHEMA\.COLUMNS", qry, re.IGNORECASE):
            cols = [("Code", "int"), ("Name", "nvarchar"), ("MasterType", "int")]
            return _rowset([{"COLUMN_NAME": c, "DATA_TYPE": d} for c, d in cols])
        if re.search(r"MasterType\s*=\s*6", qry, re.IGNORECASE):
            # fake Item list — MOCK_ITEM101_STAMP/MOCK_ITEM101_PRICE simulate a price change
            stamp101 = os.environ.get("MOCK_ITEM101_STAMP", "1001")
            return _rowset(
                [
                    {
                        "Code": "101",
                        "Name": "Fake Blender",
                        "Stamp": stamp101,
                        "BlockedMaster": "False",
                        "DeactiveMaster": "False",
                    },
                    {
                        "Code": "102",
                        "Name": "Fake Kettle",
                        "Stamp": "1002",
                        "BlockedMaster": "False",
                        "DeactiveMaster": "False",
                    },
                    {
                        "Code": "103",
                        "Name": "Fake Discontinued Item",
                        "Stamp": "1003",
                        "BlockedMaster": "True",
                        "DeactiveMaster": "False",
                    },
                ]
            )
        if re.search(r"MasterType\s*=\s*11", qry, re.IGNORECASE):
            return _rowset(
                [
                    {
                        "Code": "201",
                        "Name": "Main Store",
                        "Alias": "MS",
                        "ParentGrp": "0",
                        "BlockedMaster": "False",
                        "DeactiveMaster": "False",
                    },
                    {
                        "Code": "202",
                        "Name": "Online Warehouse",
                        "Alias": "ONL",
                        "ParentGrp": "0",
                        "BlockedMaster": "False",
                        "DeactiveMaster": "False",
                    },
                ]
            )
        return _rowset([{"VchNo": "1/2024-25"}, {"VchNo": "2/2024-25"}])

    def _respond(self, *, result: str, description: str | None, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Result", result)
        if description is not None:
            self.send_header("Description", description)
        self.send_header("Content-Type", "text/xml")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def server_host_port(server: ThreadingHTTPServer) -> tuple[str, int]:
    """`server_address` is typed loosely for socketserver's AF_UNIX case; this server is
    always AF_INET, so the host is always a str."""
    host, port = server.server_address[:2]
    return str(host), int(port)


@contextmanager
def run_mock_busy_server(host: str = "127.0.0.1", port: int = 0) -> Iterator[ThreadingHTTPServer]:
    """Start the mock BUSY server on a background thread; ``port=0`` picks a free port."""
    server = ThreadingHTTPServer((host, port), MockBusyHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        thread.join()


if __name__ == "__main__":
    from threading import Event

    with run_mock_busy_server(port=DEFAULT_PORT) as server:
        host, port = server_host_port(server)
        print(f"Mock BUSY listening on http://{host}:{port}  (Ctrl+C to stop)")
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass
