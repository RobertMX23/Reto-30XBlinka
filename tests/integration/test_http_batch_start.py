import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from blinka.http_api import make_handler


def test_http_api_accepts_batch_and_returns_id(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path / "api.db"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        payload = {"batch_id": "HTTP-START", "items": [{"document_id": "D-1", "request": {"content": "hola"}}]}
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("POST", "/batches", body=json.dumps(payload), headers={"Content-Type": "application/json"})
        response = connection.getresponse()
        body = json.loads(response.read())
        assert response.status == 202
        assert body["batch_id"] == "HTTP-START"
        assert body["state"] == "PROCESSING"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
