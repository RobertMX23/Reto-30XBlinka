"""Contratos de entrada y estados del orquestador Blinka."""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class SourceType(str, Enum):
    TEXT = "TEXT"
    TXT_FILE = "TXT_FILE"
    PDF_TEXT = "PDF_TEXT"
    PDF_SCAN = "PDF_SCAN"
    IMAGE = "IMAGE"
    EMAIL = "EMAIL"
    EMAIL_ATTACHMENT = "EMAIL_ATTACHMENT"


class WorkflowState(str, Enum):
    RECEIVED = "RECEIVED"
    CLASSIFIED = "CLASSIFIED"
    PRESERVED = "PRESERVED"
    EXTRACTING = "EXTRACTING"
    EXTRACTED = "EXTRACTED"
    PARSED = "PARSED"
    REFERENCES_LOADED = "REFERENCES_LOADED"
    REGISTERED = "REGISTERED"
    READY_FOR_DECISION = "READY_FOR_DECISION"
    PAGAR = "PAGAR"
    FRENAR = "FRENAR"
    ESCALAR = "ESCALAR"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    WAITING_HUMAN_APPROVAL = "WAITING_HUMAN_APPROVAL"
    HUMAN_APPROVED = "HUMAN_APPROVED"
    HUMAN_REJECTED = "HUMAN_REJECTED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"
    REJECTED = "REJECTED"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"


class InputRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    request_id: Optional[str] = None
    source_type: Optional[SourceType] = None
    origin: str = "CHAT"
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    path: Optional[str] = None
    content: Optional[str] = None
    message_id: Optional[str] = None
    ingest_key: Optional[str] = None
    run_decision: bool = False


class InputIssue(BaseModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class OrchestrationResult(BaseModel):
    contract_version: str = "1.0"
    request_id: Optional[str] = None
    state: WorkflowState
    source_type: Optional[SourceType] = None
    intake_id: Optional[str] = None
    receipt: Optional[dict[str, Any]] = None
    decision: Optional[dict[str, Any]] = None
    issues: list[InputIssue] = Field(default_factory=list)
    moves_money: bool = False
