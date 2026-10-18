"""Contratos de memoria: hechos estructurados, no autoridad financiera."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field


class MemoryFact(BaseModel):
    fact_id: str
    fact_type: str
    tenant_id: str
    beneficiary_id: str | None = None
    invoice_number: str | None = None
    agreement_ref: str | None = None
    content: dict[str, Any]
    source_type: str
    source_trust: Literal["VALIDATED_STRUCTURED_DATA"] = "VALIDATED_STRUCTURED_DATA"
    evidence_ids: list[str] = Field(default_factory=list)
    policy_version: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    moves_money: bool = False


class MemorySearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    tenant_id: str = Field(min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)


class MemorySearchResult(BaseModel):
    memories: list[MemoryFact] = Field(default_factory=list)
    query: str
    source: str
    authoritative: bool = False
    moves_money: bool = False
