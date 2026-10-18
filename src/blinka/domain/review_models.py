from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field

class ReviewDecision(str, Enum):
    APPROVE = "APROBAR"
    REJECT = "RECHAZAR"

class HumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    review_id: str
    batch_id: str
    document_id: str
    assigned_to: str
    state: str = "WAITING_HUMAN_APPROVAL"
    decision: ReviewDecision | None = None
    reason: str
    decided_by: str | None = None
    decided_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
