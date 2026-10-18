"""Contratos de procesamiento por lote para Blinka.

El lote coordina documentos; no sustituye el contrato individual del orquestador.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from blinka.domain.input_models import InputIssue, InputRequest, WorkflowState


class BatchState(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"


class BatchItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: str
    request: InputRequest
    state: WorkflowState = WorkflowState.RECEIVED
    attempt: int = 0
    result: Optional[dict[str, Any]] = None
    issues: list[InputIssue] = Field(default_factory=list)
    events: list[dict[str, Any]] = Field(default_factory=list)


# Nombre de contrato orientado al dominio: cada elemento del lote representa
# una factura que el orquestador debe procesar de forma independiente.
InvoiceWorkItem = BatchItem


class BatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = "1.0"
    batch_id: str
    items: list[BatchItem] = Field(min_length=1, max_length=100)
    max_concurrency: int = Field(default=4, ge=1, le=16)


class BatchResult(BaseModel):
    contract_version: str = "1.0"
    batch_id: str
    state: BatchState
    total_documents: int
    completed_documents: int
    pagar: int = 0
    frenar: int = 0
    escalar: int = 0
    failed: int = 0
    items: list[BatchItem]
    events: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    moves_money: bool = False
