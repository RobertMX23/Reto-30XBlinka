from __future__ import annotations

from blinka.adapters.firestore_batch_store import FirestoreBatchStore
from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.config import Settings
from blinka.errors import ConfigurationError


def build_batch_store(settings: Settings):
    if settings.storage_backend == "local":
        return SqliteBatchStore(settings.db_path)
    if settings.storage_backend == "firestore":
        return FirestoreBatchStore(settings.firestore_collection)
    raise ConfigurationError(f"Backend de lotes no soportado: {settings.storage_backend}")
