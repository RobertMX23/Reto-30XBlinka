"""Worker de lotes: Pub/Sub sólo transporta el identificador; Firestore contiene el agregado."""
from __future__ import annotations

from typing import Callable

from blinka.application.batch import process_and_persist_batch
from blinka.adapters.pubsub_batch_queue import consume_batch_message
from blinka.domain.batch_models import BatchRequest, BatchItem
from blinka.ports.batch_storage import BatchStore
from blinka.adapters.firestore_review_store import FirestoreReviewStore
from blinka.domain.review_models import HumanReview
import hashlib


def process_batch_message(payload: bytes | str, store: BatchStore, processor: Callable[[BatchItem], BatchItem]):
    def process(batch_id: str):
        persisted = store.get(batch_id)
        if persisted is None:
            raise ValueError(f"No existe el lote {batch_id} para procesar.")
        request = BatchRequest(batch_id=batch_id, items=persisted.items)
        result = process_and_persist_batch(request, processor, store)
        try:
            reviews = FirestoreReviewStore()
            for item in result.items:
                if item.result and item.result.get("state") == "ESCALAR":
                    review_id = "REV-" + hashlib.sha256(f"{batch_id}:{item.document_id}".encode()).hexdigest()[:16]
                    reviews.create(HumanReview(review_id=review_id, batch_id=batch_id, document_id=item.document_id, assigned_to="Sandra", reason=item.result.get("decision", {}).get("explanation", "Revisión requerida.")))
        except Exception:
            pass
        return result

    return consume_batch_message(payload, process)
