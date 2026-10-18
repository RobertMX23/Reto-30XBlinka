import json
from http.client import HTTPConnection
from threading import Thread

from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.domain.batch_models import BatchItem, BatchRequest
from blinka.domain.input_models import InputRequest
from blinka.http_api import make_handler
from http.server import ThreadingHTTPServer


def test_http_api_returns_batch_status(tmp_path):
    db_path = tmp_path / "api.db"
    store = SqliteBatchStore(db_path)
    store.create(BatchRequest(batch_id="HTTP-BATCH", items=[BatchItem(document_id="D-1", request=InputRequest(content="x"))]))
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(db_path))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("GET", "/batches/HTTP-BATCH")
        response = connection.getresponse()
        body = json.loads(response.read())
        assert response.status == 200
        assert body["result"]["batch_id"] == "HTTP-BATCH"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
