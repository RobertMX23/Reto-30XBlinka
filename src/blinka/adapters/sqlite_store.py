"""Adaptador SQLite del almacen de ingresos. Base local; NO es una solucion distribuida (F5 usara Firestore)."""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from blinka.domain.models import DecisionResult, StoredIntake
from blinka.errors import StorageError
from blinka.ports.storage import IntakeDraft, SaveResult

_SCHEMA = """
CREATE TABLE IF NOT EXISTS intakes (
    intake_id     TEXT PRIMARY KEY,
    ingest_key    TEXT NOT NULL UNIQUE,
    content_sha256 TEXT NOT NULL,
    business_key  TEXT,
    created_at    TEXT NOT NULL,
    record_json   TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_intakes_business_key ON intakes (business_key, created_at);
"""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def intake_id_for(ingest_key: str) -> str:
    """Id estable derivado de la clave de ingreso: la misma clave siempre apunta al mismo registro."""
    return "INT-" + hashlib.sha256(ingest_key.encode("utf-8")).hexdigest()[:12].upper()


class SqliteIntakeStore:
    def __init__(self, db_path: Path, clock: Callable[[], datetime] = _utc_now):
        self._path = Path(db_path)
        self._clock = clock

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._path, timeout=30, isolation_level=None)  # transacciones manuales
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with closing(self._connect()) as conn:
                conn.executescript(_SCHEMA)
        except (sqlite3.Error, OSError) as exc:
            raise StorageError(f"No se pudo inicializar la base local: {exc}") from exc

    def save(self, draft: IntakeDraft) -> SaveResult:
        key = draft.source.ingest_key
        new_sha = draft.source.sha256
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")  # un solo escritor: reintento y alta son atomicos
                try:
                    row = conn.execute("SELECT record_json, content_sha256 FROM intakes WHERE ingest_key = ?", (key,)).fetchone()
                    if row is not None:
                        existing = StoredIntake.model_validate_json(row[0])
                        outcome = "REPLAYED" if row[1] == new_sha else "CONFLICT"
                        conn.execute("COMMIT")
                        return SaveResult(outcome=outcome, record=existing, new_sha256=new_sha)  # type: ignore[arg-type]

                    earlier = [
                        r[0]
                        for r in conn.execute(
                            "SELECT intake_id FROM intakes WHERE business_key = ? ORDER BY created_at, intake_id",
                            (draft.business_key,),
                        )
                    ] if draft.business_key else []

                    record = StoredIntake(
                        intake_id=intake_id_for(key),
                        ingest_key=key,
                        revision=1,
                        created_at=self._clock(),
                        source=draft.source,
                        extraction=draft.extraction,
                        references=draft.references,
                        issues=draft.issues,
                        processing_status=draft.processing_status,
                        business_key=draft.business_key,
                        earlier_intake_ids=earlier,
                    )
                    conn.execute(
                        "INSERT INTO intakes (intake_id, ingest_key, content_sha256, business_key, created_at, record_json) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            record.intake_id,
                            key,
                            new_sha,
                            draft.business_key,
                            record.created_at.isoformat(),
                            record.model_dump_json(),
                        ),
                    )
                    conn.execute("COMMIT")
                    return SaveResult(outcome="CREATED", record=record, new_sha256=new_sha)
                except BaseException:
                    # Revertir y RELANZAR: nunca se traga la excepcion (ni se convierte en exito).
                    conn.execute("ROLLBACK")
                    raise
        except sqlite3.Error as exc:
            raise StorageError(f"Fallo al guardar el ingreso: {exc}") from exc

    def get(self, intake_id: str) -> Optional[StoredIntake]:
        try:
            with closing(self._connect()) as conn:
                row = conn.execute("SELECT record_json FROM intakes WHERE intake_id = ?", (intake_id,)).fetchone()
        except sqlite3.Error as exc:
            raise StorageError(f"Fallo al leer el ingreso: {exc}") from exc
        return StoredIntake.model_validate_json(row[0]) if row else None

    def list_all(self) -> list[StoredIntake]:
        """Devuelve los ingresos en orden estable para el calculo secuencial del demo."""
        try:
            with closing(self._connect()) as conn:
                rows = conn.execute("SELECT record_json FROM intakes ORDER BY created_at, intake_id").fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Fallo al listar ingresos: {exc}") from exc
        return [StoredIntake.model_validate_json(row[0]) for row in rows]

    def update_decision(self, intake_id: str, decision: DecisionResult) -> StoredIntake:
        """Persiste una decision sin alterar la fuente ni las referencias del ingreso."""
        try:
            with closing(self._connect()) as conn:
                conn.execute("BEGIN IMMEDIATE")
                try:
                    row = conn.execute("SELECT record_json FROM intakes WHERE intake_id = ?", (intake_id,)).fetchone()
                    if row is None:
                        raise StorageError(f"No existe el ingreso {intake_id}.")
                    record = StoredIntake.model_validate_json(row[0])
                    if record.decision is None:
                        record = record.model_copy(update={"decision": decision})
                        conn.execute(
                            "UPDATE intakes SET record_json = ? WHERE intake_id = ?",
                            (record.model_dump_json(), intake_id),
                        )
                    conn.execute("COMMIT")
                    return record
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
        except sqlite3.Error as exc:
            raise StorageError(f"Fallo al guardar la decision: {exc}") from exc
