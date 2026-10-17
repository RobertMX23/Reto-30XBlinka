"""Casos base de F2: comparacion y decision determinista sin LLM."""

from decimal import Decimal

from tests.conftest import make_service


def _text(beneficiary: str, number: str, amount: str, currency: str = "USD", due: str = "2026-10-30", agreement: str = "AC-A-001") -> str:
    return "\n".join(
        [
            f"Beneficiario: {beneficiary}",
            f"Número de factura: {number}",
            f"Importe: {amount}",
            f"Moneda: {currency}",
            f"Vencimiento: {due}",
            f"Acuerdo: {agreement}",
        ]
    )


def _ingest_and_decide(service, text: str, key: str):
    intake = service.ingest({"text": text, "ingest_key": key})
    return intake.receipt, service.decide(intake.receipt.intake_id)


def test_normal_invoice_is_paid_automatically(service):
    receipt, decision = _ingest_and_decide(service, _text("PROV-A", "F-001", "800.00"), "f2-normal")

    assert decision is not None
    assert decision.decision == "PAGAR"
    assert decision.authorization == "AUTOMATICA"
    assert decision.budget is not None
    assert decision.budget.available_after == Decimal("9200.00")
    assert service.receipt_for(receipt.intake_id).decision == decision


def test_amount_above_automatic_threshold_is_escalated(service):
    _, decision = _ingest_and_decide(
        service,
        _text("PROV-A", "F-002", "1500.00", agreement="AC-A-002"),
        "f2-threshold",
    )

    assert decision.decision == "ESCALAR"
    assert decision.authorization == "PENDIENTE"
    assert any("umbral automatico" in reason for reason in decision.reasons)
    assert decision.budget is not None and decision.budget.available_after == Decimal("10000.00")


def test_duplicate_is_stopped_without_second_commitment(service):
    text = _text("PROV-A", "F-003", "800.00")
    first, first_decision = _ingest_and_decide(service, text, "f2-duplicate-a")
    second, second_decision = _ingest_and_decide(service, text, "f2-duplicate-b")

    assert first_decision.decision == "PAGAR"
    assert second.earlier_intake_ids == [first.intake_id]
    assert second_decision.decision == "FRENAR"
    assert any("duplicado" in reason for reason in second_decision.reasons)


def test_new_beneficiary_is_escalated(service):
    _, decision = _ingest_and_decide(
        service,
        _text("PROV-N", "F-004", "500.00", agreement="AC-N-001"),
        "f2-new-beneficiary",
    )

    assert decision.decision == "ESCALAR"
    assert any("lista de beneficiarios" in reason for reason in decision.reasons)


def test_agreement_mismatch_is_stopped(service):
    _, decision = _ingest_and_decide(service, _text("PROV-A", "F-005", "900.00"), "f2-mismatch")

    assert decision.decision == "FRENAR"
    assert any("acuerdo" in reason for reason in decision.reasons)


def test_missing_due_date_is_escalated_without_inventing_a_value(service):
    text = "\n".join(
        [
            "Beneficiario: PROV-B",
            "Número de factura: F-006",
            "Importe: 450.00",
            "Moneda: USD",
            "Acuerdo: AC-B-001",
        ]
    )
    _, decision = _ingest_and_decide(service, text, "f2-missing-date")

    assert decision.decision == "ESCALAR"
    assert any("vencimiento" in reason.lower() for reason in decision.reasons)


def test_non_operating_currency_is_escalated_without_conversion(service):
    _, decision = _ingest_and_decide(
        service,
        _text("PROV-A", "F-007", "800.00", currency="MXN"),
        "f2-currency",
    )

    assert decision.decision == "ESCALAR"
    assert any("politica aplicable" in reason for reason in decision.reasons)


def test_period_budget_is_rechecked_before_a_new_approval(service):
    for index in range(12):
        _, decision = _ingest_and_decide(
            service,
            _text("PROV-A", f"F-BUDGET-{index:02d}", "800.00"),
            f"f2-budget-{index:02d}",
        )
        assert decision.decision == "PAGAR"

    _, decision = _ingest_and_decide(service, _text("PROV-A", "F-BUDGET-12", "800.00"), "f2-budget-12")

    assert decision.decision == "FRENAR"
    assert any("presupuesto" in reason for reason in decision.reasons)
    assert decision.budget is not None
    assert decision.budget.committed_before == Decimal("9600.00")
    assert decision.budget.available_after == Decimal("400.00")
