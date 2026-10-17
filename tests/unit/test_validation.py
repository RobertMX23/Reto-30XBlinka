from datetime import date
from decimal import Decimal

import pytest

from blinka.adapters.fixture_reader import parse_labeled_invoice
from blinka.domain.models import IssueCode
from blinka.domain.validation import (
    normalize_amount,
    normalize_currency,
    normalize_date,
    validate_candidate,
)


@pytest.mark.parametrize(
    "raw,value,code",
    [
        ("800.00", Decimal("800.00"), None),
        ("800", Decimal("800.00"), None),
        ("1,500.00", Decimal("1500.00"), None),
        ("1000.01", Decimal("1000.01"), None),
        ("1.500,00", None, IssueCode.INVALID_AMOUNT),  # formato europeo: ambiguo
        ("800,00", None, IssueCode.INVALID_AMOUNT),
        ("ochocientos", None, IssueCode.INVALID_AMOUNT),
        ("8OO.00", None, IssueCode.INVALID_AMOUNT),  # letra O en lugar de cero
        ("800.005", None, IssueCode.INVALID_AMOUNT),  # nunca se redondea en silencio
        ("", None, IssueCode.INVALID_AMOUNT),
        ("0.00", Decimal("0.00"), IssueCode.NON_POSITIVE_AMOUNT),
        ("-5.00", Decimal("-5.00"), IssueCode.NON_POSITIVE_AMOUNT),
    ],
)
def test_amount_is_strict(raw, value, code):
    assert normalize_amount(raw) == (value, code)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2026-10-25", date(2026, 10, 25)),
        ("2026-02-30", None),  # fecha inexistente
        ("25/10/2026", None),
        ("03/04/2026", None),  # ambigua dd/mm vs mm/dd
        ("2026-1-5", None),
        ("", None),
    ],
)
def test_date_only_unambiguous_iso(raw, expected):
    assert normalize_date(raw) == expected


@pytest.mark.parametrize("raw,expected", [("usd", "USD"), (" MXN ", "MXN"), ("US", None), ("USDX", None), ("12$", None)])
def test_currency(raw, expected):
    assert normalize_currency(raw) == expected


def _validate(text):
    return validate_candidate(parse_labeled_invoice(text))


FULL = """Beneficiario: PROV-A
Numero de factura: A-001
Importe: 800.00
Moneda: USD
Vencimiento: 2026-10-25
Acuerdo: AC-A-001
"""


def test_labels_ignore_case_and_accents_and_unknown_labels():
    text = FULL.replace("Numero de factura", "NÚMERO  DE   FACTURA") + "Observacion: nada\n"
    result = _validate(text)
    assert result.issues == []
    assert result.normalized.invoice_number == "A-001"


def test_parser_keeps_textual_evidence_with_line_numbers():
    candidate = parse_labeled_invoice("FACTURA\n" + FULL)
    amount = candidate.fields["amount"][0]
    assert (amount.value, amount.line_no, amount.line) == ("800.00", 4, "Importe: 800.00")


def test_missing_and_empty_fields_are_reported_not_invented():
    result = _validate(FULL.replace("Vencimiento: 2026-10-25\n", "Vencimiento:\n").replace("Moneda: USD\n", ""))
    codes = {(i.field, i.code) for i in result.issues}
    assert codes == {("due_date", IssueCode.MISSING_FIELD), ("currency", IssueCode.MISSING_FIELD)}
    assert result.normalized.due_date is None and result.normalized.currency is None
    assert result.normalized.amount == Decimal("800.00")  # lo demas se conserva


def test_conflicting_duplicate_label_is_ambiguous_and_not_resolved():
    result = _validate(FULL + "Importe: 1.00\n")
    assert [(i.field, i.code) for i in result.issues] == [("amount", IssueCode.AMBIGUOUS_FIELD)]
    assert result.normalized.amount is None


def test_same_value_repeated_is_not_ambiguous():
    assert _validate(FULL + "Importe: 800.00\n").issues == []


def test_non_positive_amount_is_flagged():
    result = _validate(FULL.replace("800.00", "0.00"))
    assert [i.code for i in result.issues] == [IssueCode.NON_POSITIVE_AMOUNT]
