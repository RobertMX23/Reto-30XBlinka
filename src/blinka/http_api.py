"""API HTTP mínima para consultar lotes; adaptador reemplazable en producción."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from dataclasses import replace
from urllib.parse import unquote, urlparse

from blinka.domain.batch_models import BatchRequest
from blinka.domain.input_models import InputRequest
from blinka.adapters.batch_store_factory import build_batch_store
from blinka.adapters.pubsub_batch_queue import PubSubBatchQueue
from blinka.application.batch import process_and_persist_batch
from agents.blinka_orchestrator.nodes import process_batch_item
from blinka.tools.batch_tools import get_batch_status
from blinka.config import Settings


def make_handler(db_path: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path.rstrip("/")
            if path == "/health":
                self._send(200, {"ok": True, "service": "blinka-batch-api"})
                return
            prefix = "/batches/"
            if path.startswith(prefix) and path != prefix:
                batch_id = unquote(path[len(prefix):])
                settings = replace(Settings.from_env(), db_path=db_path)
                result = get_batch_status(batch_id, db_path, store=build_batch_store(settings))
                self._send(200 if result.get("ok") else 404, result)
                return
            self._send(404, {"ok": False, "code": "NOT_FOUND", "message": "Ruta no encontrada."})

        def do_POST(self) -> None:  # noqa: N802
            if urlparse(self.path).path.rstrip("/") != "/batches":
                self._send(404, {"ok": False, "code": "NOT_FOUND", "message": "Ruta no encontrada."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length))
                request = BatchRequest.model_validate(payload)
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._send(400, {"ok": False, "code": "INVALID_BATCH", "message": str(exc)})
                return
            base_settings = Settings.from_env()
            worker_settings = replace(base_settings, db_path=db_path)
            store = build_batch_store(worker_settings)
            store.initialize()
            store.create(request)
            if worker_settings.queue_backend == "pubsub":
                if not worker_settings.gcp_project_id:
                    self._send(500, {"ok": False, "code": "CONFIGURATION_ERROR", "message": "Falta GOOGLE_CLOUD_PROJECT."})
                    return
                message_id = PubSubBatchQueue(worker_settings.gcp_project_id, worker_settings.pubsub_topic).publish_batch(request.batch_id)
                self._send(202, {"ok": True, "batch_id": request.batch_id, "state": "QUEUED", "message_id": message_id, "total_documents": len(request.items)})
                return
            Thread(target=process_and_persist_batch, args=(request, lambda item: process_batch_item(request.batch_id, item, worker_settings), store), daemon=True).start()
            self._send(202, {"ok": True, "batch_id": request.batch_id, "state": "PROCESSING", "total_documents": len(request.items)})

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(host: str = "0.0.0.0", port: int = 8090, db_path: Path | None = None) -> None:
    from blinka.config import Settings

    path = db_path or Settings.from_env().db_path
    server = ThreadingHTTPServer((host, port), make_handler(path))
    server.serve_forever()


if __name__ == "__main__":
    import os

    serve(port=int(os.environ.get("PORT", "8080")))
