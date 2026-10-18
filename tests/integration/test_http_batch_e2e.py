import json
import time
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from blinka.http_api import make_handler


def test_http_batch_start_then_status_reaches_completed(tmp_path, monkeypatch):
    monkeypatch.setenv("BLINKA_ROOT", str(tmp_path))
    monkeypatch.setenv("BLINKA_DB_PATH", str(tmp_path / "api.db"))
    reference_dir = tmp_path / "data" / "reference"
    reference_dir.mkdir(parents=True)
    repo_reference = __import__("pathlib").Path(__file__).parents[2] / "data" / "reference"
    for source in repo_reference.glob("*.json"):
        (reference_dir / source.name).write_bytes(source.read_bytes())
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path / "api.db"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    invoice = "\n".join(["Beneficiario: PROV-A", "Numero de factura: HTTP-E2E-001", "Importe: 800.00", "Moneda: USD", "Vencimiento: 2026-10-25", "Acuerdo: AC-A-001"])
    payload = {"batch_id": "HTTP-E2E", "items": [{"document_id": "DOC-1", "request": {"content": invoice}}]}
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("POST", "/batches", body=json.dumps(payload), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        assert response.status == 202
        response.read()
        for _ in range(30):
            connection.request("GET", "/batches/HTTP-E2E")
            status = connection.getresponse()
            body = json.loads(status.read())
            if body["result"]["state"] == "COMPLETED":
                assert body["result"]["pagar"] == 1
                assert body["result"]["items"][0]["result"]["decision"]["decision"] == "PAGAR"
                break
            time.sleep(0.05)
        else:
            raise AssertionError(f"El lote no terminó: {body}")
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
