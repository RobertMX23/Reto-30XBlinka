"""Worker de lotes: Pub/Sub sólo transporta el identificador; Firestore contiene el agregado."""
from __future__ import annotations

from typing import Callable

from blinka.application.batch import process_and_persist_batch
from blinka.adapters.pubsub_batch_queue import consume_batch_message
from blinka.domain.batch_models import BatchRequest, BatchItem
from blinka.ports.batch_storage import BatchStore


def process_batch_message(payload: bytes | str, store: BatchStore, processor: Callable[[BatchItem], BatchItem]):
    def process(batch_id: str):
        persisted = store.get(batch_id)
        if persisted is None:
            raise ValueError(f"No existe el lote {batch_id} para procesar.")
        request = BatchRequest(batch_id=batch_id, items=persisted.items)
        return process_and_persist_batch(request, processor, store)

    return consume_batch_message(payload, process)
