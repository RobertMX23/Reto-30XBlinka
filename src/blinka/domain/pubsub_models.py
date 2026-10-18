"""Contrato versionado de mensajes para procesamiento asíncrono de lotes."""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BatchMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = "1.0"
    batch_id: str
    operation: str = "PROCESS"

