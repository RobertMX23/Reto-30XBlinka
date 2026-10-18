"""Persistencia SQLite del estado de lotes para ejecución local."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from blinka.domain.batch_models import BatchRequest, BatchResult, BatchState
from blinka.errors import StorageError

class SqliteBatchStore:
    def __init__(self, db_path: Path): self._path = Path(db_path)
    def _connect(self): return sqlite3.connect(self._path, timeout=30, isolation_level=None)
    def initialize(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as conn:
                conn.execute("CREATE TABLE IF NOT EXISTS batches (batch_id TEXT PRIMARY KEY, state TEXT NOT NULL, result_json TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        except (sqlite3.Error, OSError) as exc:
            raise StorageError(f"No se pudo inicializar el estado de lotes: {exc}") from exc
    def create(self, request: BatchRequest) -> BatchResult:
        self.initialize()
        now = datetime.now(timezone.utc)
        result = BatchResult(batch_id=request.batch_id, state=BatchState.RECEIVED, total_documents=len(request.items), completed_documents=0, items=request.items, started_at=now)
        try:
            with closing(self._connect()) as conn:
                conn.execute("INSERT OR IGNORE INTO batches(batch_id,state,result_json,created_at,updated_at) VALUES (?,?,?,?,?)", (request.batch_id, result.state.value, result.model_dump_json(), now.isoformat(), now.isoformat()))
        except sqlite3.Error as exc:
            raise StorageError(f"No se pudo crear el lote: {exc}") from exc
        return self.get(request.batch_id) or result
    def save(self, result: BatchResult) -> BatchResult:
        try:
            with closing(self._connect()) as conn:
                conn.execute("UPDATE batches SET state=?, result_json=?, updated_at=? WHERE batch_id=?", (result.state.value, result.model_dump_json(), datetime.now(timezone.utc).isoformat(), result.batch_id))
        except sqlite3.Error as exc:
            raise StorageError(f"No se pudo guardar el lote: {exc}") from exc
        return result
    def get(self, batch_id: str) -> BatchResult | None:
        self.initialize()
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT result_json FROM batches WHERE batch_id=?", (batch_id,)).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"No se pudo consultar el lote: {exc}") from exc
        return BatchResult.model_validate_json(row[0]) if row else None
