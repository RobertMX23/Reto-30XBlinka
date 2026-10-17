"""Contratos de dominio de Blinka (F0/F1/F2). Independientes de ADK.

Principios:
- Los campos faltantes o invalidos se CONSERVAN como incidencias; nunca se convierten en valores autorizables.
- El dinero usa Decimal; las fechas son ISO-8601 estrictas.
- El estado de procesamiento (REGISTRADA...) es distinto de la decision de negocio.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blinka.errors import ConfigurationError

FIELD_NAMES = ("beneficiary", "invoice_number", "amount", "currency", "due_date", "agreement_ref")


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class IssueCode(str, Enum):
    MISSING_FIELD = "MISSING_FIELD"
    AMBIGUOUS_FIELD = "AMBIGUOUS_FIELD"
    INVALID_AMOUNT = "INVALID_AMOUNT"
    NON_POSITIVE_AMOUNT = "NON_POSITIVE_AMOUNT"
    INVALID_DATE = "INVALID_DATE"
    INVALID_CURRENCY = "INVALID_CURRENCY"
    INVALID_IDENTIFIER = "INVALID_IDENTIFIER"
    REFERENCE_NOT_FOUND = "REFERENCE_NOT_FOUND"
    ENCODING_FALLBACK = "ENCODING_FALLBACK"


class ProcessingStatus(str, Enum):
    """Estado de procesamiento del ingreso. NO es una decision de pago."""

    REGISTRADA = "REGISTRADA"
    REGISTRADA_CON_INCIDENCIAS = "REGISTRADA_CON_INCIDENCIAS"


class FieldIssue(_Model):
    field: str
    code: IssueCode
    message: str
    raw_value: Optional[str] = None  # representacion original, conservada tal cual


class SourceDocument(_Model):
    """Fuente original conservada ANTES de interpretarla."""

    ingest_key: str
    origin: str  # ruta relativa al directorio de facturas, o "inline"
    text: str
    encoding: Literal["utf-8", "latin-1"]
    sha256: str  # huella de los bytes originales
    byte_length: int


class RawField(_Model):
    label: str
    value: str
    line_no: int
    line: str  # evidencia textual


class ExtractionCandidate(_Model):
    """Lo que el parser encontro, sin interpretar. Cada campo puede aparecer 0..n veces."""

    fields: Dict[str, List[RawField]] = Field(default_factory=dict)


class NormalizedInvoice(_Model):
    beneficiary_id: Optional[str] = None
    invoice_number: Optional[str] = None
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    due_date: Optional[date] = None
    agreement_ref: Optional[str] = None


class ExtractionResult(_Model):
    candidate: ExtractionCandidate
    normalized: NormalizedInvoice
    issues: List[FieldIssue] = Field(default_factory=list)


class Policy(_Model):
    """Politica versionada. F2 la aplica solo para decisiones simuladas."""

    version: str
    company: str
    operating_currency: str
    period: str
    auto_threshold: Decimal
    max_per_invoice: Decimal
    period_budget: Decimal
    allowed_beneficiaries: List[str]
    synthetic: bool = True

    @model_validator(mode="after")
    def _check(self) -> "Policy":
        for name in ("auto_threshold", "max_per_invoice", "period_budget"):
            if getattr(self, name) < 0:
                raise ConfigurationError(f"Politica {self.version}: {name} no puede ser negativo")
        if self.auto_threshold > self.max_per_invoice:
            raise ConfigurationError(
                f"Politica {self.version}: el umbral automatico no puede exceder el maximo por factura"
            )
        if not self.synthetic:
            raise ConfigurationError("Solo se admiten politicas marcadas como sinteticas (synthetic=true)")
        return self


class Beneficiary(_Model):
    beneficiary_id: str
    name: str
    country: Optional[str] = None
    synthetic: bool = True


class Agreement(_Model):
    agreement_ref: str
    beneficiary_id: str
    amount: Decimal
    currency: str
    synthetic: bool = True


class ReferenceHit(_Model):
    """Resultado de consultar UNA referencia por identificador."""

    requested_id: Optional[str]
    found: bool
    record: Optional[dict] = None


class ReferenceLookup(_Model):
    policy_version: str
    policy_sha256: str
    beneficiary: ReferenceHit
    agreement: ReferenceHit
    issues: List[FieldIssue] = Field(default_factory=list)


class StoredIntake(_Model):
    """Registro completo y recuperable de un ingreso."""

    intake_id: str
    ingest_key: str
    revision: int
    created_at: datetime
    source: SourceDocument
    extraction: ExtractionResult
    references: ReferenceLookup
    issues: List[FieldIssue]  # extraccion + referencias
    processing_status: ProcessingStatus
    business_key: Optional[str] = None
    earlier_intake_ids: List[str] = Field(default_factory=list)
    decision: Optional["DecisionResult"] = None


RuleResult = Literal["CUMPLE", "INCUMPLE", "NO_EVALUABLE", "NO_APLICA"]
DecisionCode = Literal["PAGAR", "FRENAR", "ESCALAR"]
AuthorizationMode = Literal["AUTOMATICA", "HUMANA", "PENDIENTE"]


class RuleEvaluation(_Model):
    """Resultado legible de una regla determinista, con evidencia observable."""

    rule_id: str
    result: RuleResult
    evidence: str


class BudgetSnapshot(_Model):
    period: str
    currency: str
    configured: Decimal
    committed_before: Decimal
    amount: Decimal
    available_before: Decimal
    available_after: Decimal


class DecisionResult(_Model):
    """Decision F2. Siempre es simulada: nunca inicia un movimiento de dinero."""

    decision: DecisionCode
    authorization: AuthorizationMode
    policy_version: str
    period: str
    rules: List[RuleEvaluation] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    explanation: str
    budget: Optional[BudgetSnapshot] = None
    evaluated_at: datetime
    llm_used: Literal[False] = False
    moves_money: Literal[False] = False


# StoredIntake refers to DecisionResult by name so the F1 record remains
# compatible with records created before the decision phase existed.
StoredIntake.model_rebuild()


class IntakeReceipt(_Model):
    """Recibo recuperable de ingreso y, desde F2, de decision simulada."""

    intake_id: str
    revision: int
    processing_status: ProcessingStatus
    source: Dict[str, object]
    fields: Dict[str, Optional[str]]
    raw_fields: Dict[str, List[str]]
    issues: List[FieldIssue]
    references: Dict[str, object]
    policy_version: str
    business_key: Optional[str]
    earlier_intake_ids: List[str]
    created_at: datetime
    decision: Optional[DecisionResult] = None
    llm_used: Literal[False] = False
    moves_money: Literal[False] = False


def derive_status(issues: List[FieldIssue]) -> ProcessingStatus:
    return ProcessingStatus.REGISTRADA_CON_INCIDENCIAS if issues else ProcessingStatus.REGISTRADA


def make_business_key(n: NormalizedInvoice) -> Optional[str]:
    """Identidad comercial del cobro (beneficiario + numero de factura). Distinta de la huella del archivo."""
    if n.beneficiary_id and n.invoice_number:
        return f"{n.beneficiary_id}|{n.invoice_number.upper()}"
    return None
