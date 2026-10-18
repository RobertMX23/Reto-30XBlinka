"""Receptor HTTP para mensajes push de Pub/Sub en Cloud Run."""
from __future__ import annotations

import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from agents.blinka_orchestrator.nodes import process_batch_item
from blinka.adapters.batch_store_factory import build_batch_store
from blinka.application.pubsub_worker import process_batch_message
from blinka.config import Settings


def make_handler():
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict):
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path.rstrip("/") == "/health":
                self._send(200, {"ok": True, "service": "blinka-worker"})
                return
            self._send(404, {"ok": False, "code": "NOT_FOUND"})

        def do_POST(self):  # noqa: N802
            try:
                length = int(self.headers.get("Content-Length", "0"))
                envelope = json.loads(self.rfile.read(length))
                encoded = envelope["message"]["data"]
                payload = base64.b64decode(encoded)
                settings = Settings.from_env()
                store = build_batch_store(settings)
                store.initialize()
                result = process_batch_message(
                    payload, store,
                    lambda item: process_batch_item(result_batch_id(payload), item, settings),
                )
                self._send(200, {"ok": True, "batch_id": result.batch_id, "state": result.state.value})
            except Exception as exc:
                self._send(500, {"ok": False, "code": "WORKER_FAILED", "message": str(exc)})

        def log_message(self, format, *args):
            return

    return Handler


def result_batch_id(payload: bytes) -> str:
    return json.loads(payload.decode("utf-8"))["batch_id"]


def serve():
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8080"))), make_handler())
    server.serve_forever()


if __name__ == "__main__":
    serve()
