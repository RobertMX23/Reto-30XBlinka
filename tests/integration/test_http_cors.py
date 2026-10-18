from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread

from blinka.http_api import make_handler


def test_http_api_allows_frontend_cors_preflight(tmp_path):
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(tmp_path / "api.db"))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        connection = HTTPConnection("127.0.0.1", server.server_port)
        connection.request("OPTIONS", "/batches")
        response = connection.getresponse()
        assert response.status == 204
        assert response.getheader("Access-Control-Allow-Origin") == "*"
        connection.close()
    finally:
        server.shutdown()
        server.server_close()
