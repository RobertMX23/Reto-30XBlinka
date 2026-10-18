"""Tools de consulta de lotes; no ejecutan ni reintentan documentos."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from blinka.adapters.sqlite_batch_store import SqliteBatchStore


def get_batch_status(batch_id: str, db_path: str | Path) -> dict[str, Any]:
    """Devuelve el estado agregado y el detalle por documento de un lote."""
    store = SqliteBatchStore(Path(db_path))
    result = store.get(batch_id)
    if result is None:
        return {"ok": False, "code": "BATCH_NOT_FOUND", "message": f"No existe el lote {batch_id}."}
    return {"ok": True, "result": result.model_dump(mode="json"), "evidence": {"batch_id": batch_id}}
