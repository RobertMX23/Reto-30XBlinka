"""Contrato determinista para validar seguridad e integridad básica de PDFs."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class BoundaryStatus(str, Enum):
    PASS = "PASS"
    BLOCK = "BLOCK"
    ESCALATE = "ESCALATE"


class PdfSecurityStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class PdfBoundaryResult(BaseModel):
    boundary_id: str
    category: str
    status: BoundaryStatus
    reason_code: str
    message: str
    evidence: dict[str, Any] = Field(default_factory=dict)
    page_numbers: list[int] = Field(default_factory=list)
    retryable: bool = False
    next_state: str


class PdfSecurityBoundaryResult(BaseModel):
    contract_version: str = "1.0"
    document_id: str
    source_type: str = "PDF_TEXT"
    security_status: PdfSecurityStatus
    next_state: str
    boundaries: list[PdfBoundaryResult] = Field(default_factory=list)
    content_sha256: str
    page_count: int
    extracted_text_bytes: int
    moves_money: bool = False

