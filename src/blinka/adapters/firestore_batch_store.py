"""Persistencia Firestore para Cloud Run; el cliente se crea de forma diferida."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from blinka.domain.batch_models import BatchRequest, BatchResult, BatchState
from blinka.errors import StorageError


class FirestoreBatchStore:
    def __init__(self, collection: str = "batches", *, client: Any | None = None):
        self._collection_name = collection
        self._client = client

    def _collection(self):
        if self._client is None:
            try:
                from google.cloud import firestore
                self._client = firestore.Client()
            except Exception as exc:  # pragma: no cover - depende de ADC/GCP
                raise StorageError(f"No se pudo conectar con Firestore: {exc}") from exc
        return self._client.collection(self._collection_name)

    def initialize(self) -> None:
        self._collection()

    def create(self, request: BatchRequest) -> BatchResult:
        now = datetime.now(timezone.utc)
        result = BatchResult(batch_id=request.batch_id, state=BatchState.RECEIVED,
                             total_documents=len(request.items), completed_documents=0,
                             items=request.items, started_at=now)
        try:
            ref = self._collection().document(request.batch_id)
            if not ref.get().exists:
                ref.set(self._payload(result, now))
            return self.get(request.batch_id) or result
        except Exception as exc:
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"No se pudo crear el lote en Firestore: {exc}") from exc

    def save(self, result: BatchResult) -> BatchResult:
        try:
            self._collection().document(result.batch_id).set(
                self._payload(result, datetime.now(timezone.utc)), merge=True
            )
            return result
        except Exception as exc:
            raise StorageError(f"No se pudo guardar el lote en Firestore: {exc}") from exc

    def get(self, batch_id: str) -> BatchResult | None:
        try:
            snapshot = self._collection().document(batch_id).get()
            if not snapshot.exists:
                return None
            return BatchResult.model_validate_json(snapshot.to_dict()["result_json"])
        except Exception as exc:
            if isinstance(exc, StorageError):
                raise
            raise StorageError(f"No se pudo consultar el lote en Firestore: {exc}") from exc

    @staticmethod
    def _payload(result: BatchResult, now: datetime) -> dict[str, Any]:
        return {"batch_id": result.batch_id, "state": result.state.value,
                "result_json": result.model_dump_json(), "updated_at": now}
