"""API HTTP mínima para consultar lotes; adaptador reemplazable en producción."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from blinka.tools.batch_tools import get_batch_status


def make_handler(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/")
            if path == "/health":
                self._send(200, {"ok": True, "service": "blinka-batch-api"})
                return
            prefix = "/batches/"
            if path.startswith(prefix) and path != prefix:
                batch_id = unquote(path[len(prefix):])
                result = get_batch_status(batch_id, db_path)
                self._send(200 if result.get("ok") else 404, result)
                return
            self._send(404, {"ok": False, "code": "NOT_FOUND", "message": "Ruta no encontrada."})

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(host: str = "0.0.0.0", port: int = 8090, db_path: Path | None = None) -> None:
    from blinka.config import Settings

    path = db_path or Settings.from_env().db_path
    server = ThreadingHTTPServer((host, port), make_handler(path))
    server.serve_forever()
