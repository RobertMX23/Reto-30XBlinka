"""Publicador y consumidor Pub/Sub para lotes de Blinka."""
from __future__ import annotations

import json
from typing import Any, Callable

from blinka.domain.pubsub_models import BatchMessage
from blinka.errors import ConfigurationError, StorageError


class PubSubBatchQueue:
    def __init__(self, project_id: str, topic: str = "blinka-batch", *, publisher: Any | None = None):
        self.project_id, self.topic = project_id, topic
        self._publisher = publisher

    def _client(self):
        if self._publisher is None:
            try:
                from google.cloud import pubsub_v1
                self._publisher = pubsub_v1.PublisherClient()
            except Exception as exc:  # pragma: no cover - depende de ADC/GCP
                raise ConfigurationError(f"No se pudo crear el publicador Pub/Sub: {exc}") from exc
        return self._publisher

    def publish_batch(self, batch_id: str) -> str:
        message = BatchMessage(batch_id=batch_id).model_dump_json().encode("utf-8")
        path = self._client().topic_path(self.project_id, self.topic)
        try:
            return self._client().publish(path, message, batch_id=batch_id).result()
        except Exception as exc:
            raise StorageError(f"No se pudo publicar el lote en Pub/Sub: {exc}") from exc


def consume_batch_message(payload: bytes | str, process: Callable[[str], Any]) -> Any:
    """Valida el contrato del mensaje antes de entregar el batch_id al worker."""
    try:
        message = BatchMessage.model_validate_json(payload)
    except Exception as exc:
        raise ValueError(f"Mensaje Pub/Sub inválido: {exc}") from exc
    if message.operation != "PROCESS":
        raise ValueError(f"Operación Pub/Sub no soportada: {message.operation}")
    return process(message.batch_id)
