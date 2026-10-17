"""Validacion y normalizacion de campos. Estricta: ante la duda, incidencia; nunca un valor inventado."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple

from blinka.domain.models import (
    FIELD_NAMES,
    ExtractionCandidate,
    ExtractionResult,
    FieldIssue,
    IssueCode,
    NormalizedInvoice,
)

# Importe: punto decimal, hasta 2 decimales, comas solo como separador de miles. "800,00" es ambiguo -> invalido.
_AMOUNT_RE = re.compile(r"^-?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CURRENCY_RE = re.compile(r"^[A-Za-z]{3}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_INVOICE_NO_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,63}$")

_CENT = Decimal("0.01")

_LABEL_TEXT = {
    "beneficiary": "beneficiario",
    "invoice_number": "numero de factura",
    "amount": "importe",
    "currency": "moneda",
    "due_date": "vencimiento",
    "agreement_ref": "acuerdo",
}


def normalize_amount(raw: str) -> Tuple[Optional[Decimal], Optional[IssueCode]]:
    text = raw.strip()
    if not _AMOUNT_RE.match(text):
        return None, IssueCode.INVALID_AMOUNT
    try:
        value = Decimal(text.replace(",", "")).quantize(_CENT)
    except InvalidOperation:  # pragma: no cover - la expresion regular ya lo impide
        return None, IssueCode.INVALID_AMOUNT
    if value <= 0:
        return value, IssueCode.NON_POSITIVE_AMOUNT
    return value, None


def normalize_date(raw: str) -> Optional[date]:
    text = raw.strip()
    if not _DATE_RE.match(text):
        return None  # solo ISO AAAA-MM-DD: "03/04/2026" es ambiguo
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None  # p. ej. 2026-02-30


def normalize_currency(raw: str) -> Optional[str]:
    text = raw.strip()
    return text.upper() if _CURRENCY_RE.match(text) else None


def normalize_id(raw: str) -> Optional[str]:
    text = raw.strip()
    return text.upper() if _ID_RE.match(text) else None


def normalize_invoice_number(raw: str) -> Optional[str]:
    text = raw.strip()
    return text if _INVOICE_NO_RE.match(text) else None


def _select(candidate: ExtractionCandidate, name: str, issues: List[FieldIssue]) -> Optional[str]:
    """Elige el valor crudo de un campo o registra incidencia (faltante, vacio o ambiguo)."""
    occurrences = candidate.fields.get(name, [])
    label = _LABEL_TEXT[name]
    if not occurrences:
        issues.append(FieldIssue(field=name, code=IssueCode.MISSING_FIELD, message=f"Falta el campo '{label}'."))
        return None
    distinct = {o.value.strip() for o in occurrences}
    if len(distinct) > 1:
        issues.append(
            FieldIssue(
                field=name,
                code=IssueCode.AMBIGUOUS_FIELD,
                message=f"El campo '{label}' aparece con valores distintos; no se elige ninguno.",
                raw_value=" | ".join(sorted(distinct)),
            )
        )
        return None
    value = next(iter(distinct))
    if value == "":
        issues.append(
            FieldIssue(field=name, code=IssueCode.MISSING_FIELD, message=f"El campo '{label}' esta vacio.", raw_value="")
        )
        return None
    return value


def validate_candidate(candidate: ExtractionCandidate) -> ExtractionResult:
    """Convierte el candidato crudo en campos normalizados + incidencias. No lanza por contenido invalido."""
    issues: List[FieldIssue] = []
    raw: Dict[str, Optional[str]] = {name: _select(candidate, name, issues) for name in FIELD_NAMES}

    beneficiary = invoice_number = currency = agreement = None
    amount = None
    due = None

    if raw["beneficiary"] is not None:
        beneficiary = normalize_id(raw["beneficiary"])
        if beneficiary is None:
            issues.append(_bad(IssueCode.INVALID_IDENTIFIER, "beneficiary", raw["beneficiary"], "Identificador de beneficiario invalido."))
    if raw["invoice_number"] is not None:
        invoice_number = normalize_invoice_number(raw["invoice_number"])
        if invoice_number is None:
            issues.append(_bad(IssueCode.INVALID_IDENTIFIER, "invoice_number", raw["invoice_number"], "Numero de factura invalido."))
    if raw["agreement_ref"] is not None:
        agreement = normalize_id(raw["agreement_ref"])
        if agreement is None:
            issues.append(_bad(IssueCode.INVALID_IDENTIFIER, "agreement_ref", raw["agreement_ref"], "Referencia de acuerdo invalida."))
    if raw["currency"] is not None:
        currency = normalize_currency(raw["currency"])
        if currency is None:
            issues.append(_bad(IssueCode.INVALID_CURRENCY, "currency", raw["currency"], "La moneda debe ser un codigo de 3 letras (p. ej. USD)."))
    if raw["amount"] is not None:
        amount, code = normalize_amount(raw["amount"])
        if code is IssueCode.INVALID_AMOUNT:
            issues.append(_bad(code, "amount", raw["amount"], "Importe no interpretable de forma inequivoca (se espera 1234.56)."))
        elif code is IssueCode.NON_POSITIVE_AMOUNT:
            issues.append(_bad(code, "amount", raw["amount"], "El importe debe ser mayor que cero."))
    if raw["due_date"] is not None:
        due = normalize_date(raw["due_date"])
        if due is None:
            issues.append(_bad(IssueCode.INVALID_DATE, "due_date", raw["due_date"], "Fecha no valida; se espera AAAA-MM-DD existente."))

    normalized = NormalizedInvoice(
        beneficiary_id=beneficiary,
        invoice_number=invoice_number,
        amount=amount,
        currency=currency,
        due_date=due,
        agreement_ref=agreement,
    )
    return ExtractionResult(candidate=candidate, normalized=normalized, issues=issues)


def _bad(code: IssueCode, field: str, raw: str, message: str) -> FieldIssue:
    return FieldIssue(field=field, code=code, message=message, raw_value=raw)
