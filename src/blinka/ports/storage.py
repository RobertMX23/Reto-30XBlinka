"""Interfaces minimas de almacenamiento y referencias. SQLite es el adaptador local; Firestore sera el de nube (F5)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Literal, Optional, Protocol

from blinka.domain.models import (
    Agreement,
    DecisionResult,
    Beneficiary,
    ExtractionResult,
    FieldIssue,
    Policy,
    ProcessingStatus,
    ReferenceLookup,
    SourceDocument,
    StoredIntake,
)

SaveOutcome = Literal["CREATED", "REPLAYED", "CONFLICT"]


@dataclass(frozen=True)
class IntakeDraft:
    """Lo que la capa de aplicacion entrega al almacen; el almacen asigna id, revision y fecha."""

    source: SourceDocument
    extraction: ExtractionResult
    references: ReferenceLookup
    issues: List[FieldIssue]
    processing_status: ProcessingStatus
    business_key: Optional[str]


@dataclass(frozen=True)
class SaveResult:
    outcome: SaveOutcome
    record: StoredIntake  # el registro nuevo, o el ya existente si fue repeticion/conflicto
    new_sha256: str


class IntakeStore(Protocol):
    def initialize(self) -> None: ...

    def save(self, draft: IntakeDraft) -> SaveResult:
        """Atomico. Misma clave + mismo contenido -> REPLAYED (sin duplicar). Misma clave + otro contenido -> CONFLICT (sin sobrescribir)."""
        ...

    def get(self, intake_id: str) -> Optional[StoredIntake]: ...

    def list_all(self) -> List[StoredIntake]: ...

    def update_decision(self, intake_id: str, decision: DecisionResult) -> StoredIntake: ...


class ReferenceSource(Protocol):
    def get_policy(self) -> "tuple[Policy, str]":
        """Devuelve la politica vigente y la huella (sha256) del archivo que la contiene."""
        ...

    def get_beneficiary(self, beneficiary_id: str) -> Optional[Beneficiary]: ...

    def get_agreement(self, agreement_ref: str) -> Optional[Agreement]: ...
