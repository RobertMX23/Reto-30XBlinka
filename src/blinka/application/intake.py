"""Servicio de ingreso (F1). Independiente de ADK: el workflow solo llama a estos pasos.

Pasos: read_source -> extract (parsear + validar) -> load_references -> save -> receipt_for.
Ningun paso decide, compara para autorizar ni usa un LLM.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, model_validator

from blinka.application.decision import DecisionService
from blinka.adapters.fixture_reader import build_source, parse_labeled_invoice, read_source_file
from blinka.config import Settings
from blinka.domain.models import (
    ExtractionResult,
    FieldIssue,
    IntakeReceipt,
    IssueCode,
    ReferenceHit,
    ReferenceLookup,
    SourceDocument,
    StoredIntake,
    derive_status,
    make_business_key,
)
from blinka.domain.validation import validate_candidate
from blinka.errors import IngestConflictError, InvalidRequestError, SourceTooLargeError, StorageError
from blinka.ports.storage import IntakeDraft, IntakeStore, ReferenceSource, SaveResult


class IngestRequest(BaseModel):
    """Entrada: una ruta dentro del directorio autorizado, O texto de prueba. `ingest_key` es opcional."""

    model_config = ConfigDict(extra="forbid")

    path: Optional[str] = None
    text: Optional[str] = None
    ingest_key: Optional[str] = None

    @model_validator(mode="after")
    def _one_source(self) -> "IngestRequest":
        if (self.path is None) == (self.text is None):
            raise ValueError("Indica exactamente uno: 'path' o 'text'.")
        return self


@dataclass(frozen=True)
class IngestResult:
    outcome: str  # CREATED | REPLAYED
    receipt: IntakeReceipt


class IntakeService:
    def __init__(self, settings: Settings, store: IntakeStore, references: ReferenceSource):
        self._settings = settings
        self._store = store
        self._refs = references

    # 1. Leer y conservar -----------------------------------------------------------------
    def read_source(self, request: IngestRequest | dict) -> SourceDocument:
        try:
            req = request if isinstance(request, IngestRequest) else IngestRequest.model_validate(request)
        except ValueError as exc:
            raise InvalidRequestError(str(exc)) from exc
        if req.path is not None:
            return read_source_file(
                self._settings.invoices_dir,
                self._settings.root,
                req.path,
                max_bytes=self._settings.max_source_bytes,
                ingest_key=req.ingest_key,
            )
        data = (req.text or "").encode("utf-8")
        if len(data) > self._settings.max_source_bytes:
            raise SourceTooLargeError(f"El texto excede {self._settings.max_source_bytes} bytes.")
        key = req.ingest_key or "text:" + hashlib.sha256(data).hexdigest()[:16]
        return build_source(data, origin="inline", ingest_key=key)

    # 2. Parsear y validar ----------------------------------------------------------------
    def extract(self, source: SourceDocument) -> ExtractionResult:
        result = validate_candidate(parse_labeled_invoice(source.text))
        if source.encoding != "utf-8":
            issue = FieldIssue(
                field="source",
                code=IssueCode.ENCODING_FALLBACK,
                message="El archivo no es UTF-8 valido; se leyo como latin-1. Revise los acentos.",
            )
            result = result.model_copy(update={"issues": [issue, *result.issues]})
        return result

    # 3. Cargar referencias (solo consulta; no compara para autorizar) --------------------
    def load_references(self, extraction: ExtractionResult) -> ReferenceLookup:
        policy, policy_sha = self._refs.get_policy()
        n = extraction.normalized
        issues: List[FieldIssue] = []

        ben_hit = ReferenceHit(requested_id=n.beneficiary_id, found=False)
        if n.beneficiary_id:
            found = self._refs.get_beneficiary(n.beneficiary_id)
            ben_hit = ReferenceHit(
                requested_id=n.beneficiary_id, found=found is not None, record=found.model_dump(mode="json") if found else None
            )
            if not ben_hit.found:
                issues.append(
                    FieldIssue(
                        field="beneficiary",
                        code=IssueCode.REFERENCE_NOT_FOUND,
                        message=f"El beneficiario '{n.beneficiary_id}' no existe en las referencias.",
                        raw_value=n.beneficiary_id,
                    )
                )

        agr_hit = ReferenceHit(requested_id=n.agreement_ref, found=False)
        if n.agreement_ref:
            found_a = self._refs.get_agreement(n.agreement_ref)
            agr_hit = ReferenceHit(
                requested_id=n.agreement_ref, found=found_a is not None, record=found_a.model_dump(mode="json") if found_a else None
            )
            if not agr_hit.found:
                issues.append(
                    FieldIssue(
                        field="agreement_ref",
                        code=IssueCode.REFERENCE_NOT_FOUND,
                        message=f"El acuerdo '{n.agreement_ref}' no existe en las referencias; no se infiere ninguno.",
                        raw_value=n.agreement_ref,
                    )
                )

        return ReferenceLookup(
            policy_version=policy.version, policy_sha256=policy_sha, beneficiary=ben_hit, agreement=agr_hit, issues=issues
        )

    # 4. Guardar --------------------------------------------------------------------------
    def save(self, source: SourceDocument, extraction: ExtractionResult, lookup: ReferenceLookup) -> SaveResult:
        issues = [*extraction.issues, *lookup.issues]
        draft = IntakeDraft(
            source=source,
            extraction=extraction,
            references=lookup,
            issues=issues,
            processing_status=derive_status(issues),
            business_key=make_business_key(extraction.normalized),
        )
        return self._store.save(draft)

    # 5. Recuperar y emitir recibo --------------------------------------------------------
    def receipt_for(self, intake_id: str) -> Optional[IntakeReceipt]:
        record = self._store.get(intake_id)
        return None if record is None else build_receipt(record)

    def get_record(self, intake_id: str) -> Optional[StoredIntake]:
        return self._store.get(intake_id)

    def decide(self, intake_id: str):
        """Evalua y persiste la decision determinista F2, sin ejecutar pagos."""
        return DecisionService(self._store, self._refs).decide(intake_id)

    # Composicion completa (sin ADK) ---------------------------------------------------------
    def ingest(self, request: IngestRequest | dict) -> IngestResult:
        source = self.read_source(request)
        extraction = self.extract(source)
        lookup = self.load_references(extraction)
        saved = self.save(source, extraction, lookup)
        if saved.outcome == "CONFLICT":
            raise conflict_error(saved)
        receipt = self.receipt_for(saved.record.intake_id)
        if receipt is None:  # no deberia ocurrir: acabamos de guardarlo
            raise StorageError("El ingreso se guardo pero no pudo recuperarse.")
        return IngestResult(outcome=saved.outcome, receipt=receipt)


def conflict_error(saved: SaveResult) -> IngestConflictError:
    return IngestConflictError(
        "La clave de ingreso ya existe con contenido distinto; no se sobrescribe la fuente anterior.",
        intake_id=saved.record.intake_id,
        existing_sha256=saved.record.source.sha256,
        new_sha256=saved.new_sha256,
    )


def build_receipt(record: StoredIntake) -> IntakeReceipt:
    n = record.extraction.normalized
    return IntakeReceipt(
        intake_id=record.intake_id,
        revision=record.revision,
        processing_status=record.processing_status,
        source={
            "ingest_key": record.source.ingest_key,
            "origin": record.source.origin,
            "sha256": record.source.sha256,
            "byte_length": record.source.byte_length,
            "encoding": record.source.encoding,
        },
        fields={
            "beneficiary_id": n.beneficiary_id,
            "invoice_number": n.invoice_number,
            "amount": None if n.amount is None else str(n.amount),
            "currency": n.currency,
            "due_date": None if n.due_date is None else n.due_date.isoformat(),
            "agreement_ref": n.agreement_ref,
        },
        raw_fields={name: [f.value for f in occ] for name, occ in record.extraction.candidate.fields.items()},
        issues=record.issues,
        references={
            "policy_version": record.references.policy_version,
            "policy_sha256": record.references.policy_sha256,
            "beneficiary": record.references.beneficiary.model_dump(mode="json"),
            "agreement": record.references.agreement.model_dump(mode="json"),
        },
        policy_version=record.references.policy_version,
        business_key=record.business_key,
        earlier_intake_ids=record.earlier_intake_ids,
        created_at=record.created_at,
        decision=record.decision,
    )
