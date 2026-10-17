"""Evaluador determinista F2.

Esta capa convierte un ingreso ya conservado en una decision simulada. No usa un
LLM, no interpreta instrucciones del documento y nunca ejecuta un pago. El orden
de precedencia es: impedimento duro -> ESCALAR por datos o excepcion -> PAGAR.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterable, List, Optional

from blinka.domain.models import (
    BudgetSnapshot,
    DecisionResult,
    Policy,
    RuleEvaluation,
    StoredIntake,
)
from blinka.ports.storage import IntakeStore, ReferenceSource


def _money(value: Decimal) -> str:
    return f"{value:.2f}"


def _rule(rules: List[RuleEvaluation], rule_id: str, result: str, evidence: str) -> None:
    rules.append(RuleEvaluation(rule_id=rule_id, result=result, evidence=evidence))  # type: ignore[arg-type]


def _committed(records: Iterable[StoredIntake], policy: Policy) -> Decimal:
    total = Decimal("0")
    for item in records:
        decision = item.decision
        if decision is None or decision.decision != "PAGAR":
            continue
        if decision.period != policy.period:
            continue
        n = item.extraction.normalized
        if n.currency and n.currency.upper() == policy.operating_currency.upper() and n.amount is not None:
            total += n.amount
    return total


def evaluate_record(record: StoredIntake, policy: Policy, records: Iterable[StoredIntake]) -> DecisionResult:
    """Evalua un registro con una politica y el historial visible en el almacen."""

    n = record.extraction.normalized
    rules: List[RuleEvaluation] = []
    hard_reasons: List[str] = []
    pending_reasons: List[str] = []

    invalid_codes = {"INVALID_AMOUNT", "NON_POSITIVE_AMOUNT", "INVALID_CURRENCY", "INVALID_IDENTIFIER"}
    missing_codes = {"MISSING_FIELD", "AMBIGUOUS_FIELD", "INVALID_DATE"}
    for issue in record.issues:
        if issue.code.value in invalid_codes:
            hard_reasons.append(issue.message)
        elif issue.code.value in missing_codes or issue.code.value == "REFERENCE_NOT_FOUND":
            pending_reasons.append(issue.message)

    if hard_reasons:
        _rule(rules, "R01", "INCUMPLE", "; ".join(hard_reasons))
    elif pending_reasons:
        _rule(rules, "R01", "NO_EVALUABLE", "; ".join(pending_reasons))
    else:
        _rule(rules, "R01", "CUMPLE", "Los campos necesarios son validos y estan disponibles.")

    if record.earlier_intake_ids:
        hard_reasons.append(
            f"Cobro duplicado: {record.business_key} ya aparece en {', '.join(record.earlier_intake_ids)}."
        )
        _rule(rules, "R02", "INCUMPLE", "Cobro duplicado; no se compromete presupuesto otra vez.")
    else:
        _rule(rules, "R02", "CUMPLE", "No se encontro un ingreso anterior con la misma identidad comercial.")

    currency = n.currency.upper() if n.currency else None
    policy_currency = policy.operating_currency.upper()
    if currency is None:
        _rule(rules, "R03", "NO_EVALUABLE", "No hay moneda para seleccionar una politica compatible.")
        pending_reasons.append("Falta la moneda de la factura.")
    elif currency != policy_currency:
        _rule(rules, "R03", "NO_EVALUABLE", f"La factura esta en {currency}; la politica vigente opera en {policy_currency}.")
        pending_reasons.append(f"No existe una politica aplicable para {currency}; no se convierte implicitamente.")
    elif not record.references.agreement.found or not record.references.beneficiary.found:
        _rule(rules, "R03", "NO_EVALUABLE", "Falta una referencia necesaria de beneficiario o acuerdo.")
        pending_reasons.append("Completar la referencia de beneficiario o acuerdo antes de evaluar.")
    else:
        _rule(rules, "R03", "CUMPLE", f"La politica {policy.version} aplica a {policy_currency}.")

    agreement = record.references.agreement.record
    if currency is not None and currency != policy_currency:
        _rule(rules, "R04", "NO_EVALUABLE", "La moneda no tiene una politica compatible; no se compara contra un acuerdo USD.")
    elif agreement is None or n.amount is None or n.beneficiary_id is None or currency is None:
        _rule(rules, "R04", "NO_EVALUABLE", "No hay datos suficientes para comparar la factura con el acuerdo.")
    else:
        mismatches: List[str] = []
        if str(agreement.get("beneficiary_id", "")).upper() != n.beneficiary_id.upper():
            mismatches.append("beneficiario")
        if str(agreement.get("currency", "")).upper() != currency:
            mismatches.append("moneda")
        try:
            agreement_amount = Decimal(str(agreement.get("amount")))
        except Exception:
            agreement_amount = None
        if agreement_amount is None or agreement_amount != n.amount:
            mismatches.append("importe")
        if mismatches:
            hard_reasons.append("La factura no coincide con el acuerdo en " + ", ".join(mismatches) + ".")
            _rule(rules, "R04", "INCUMPLE", hard_reasons[-1])
        else:
            _rule(rules, "R04", "CUMPLE", f"Coincide exactamente con {record.references.agreement.requested_id}.")

    if n.amount is None:
        _rule(rules, "R05", "NO_EVALUABLE", "No hay importe para comparar con el maximo por factura.")
    elif n.amount > policy.max_per_invoice:
        reason = f"{_money(n.amount)} {policy_currency} supera el maximo duro de {_money(policy.max_per_invoice)} {policy_currency}."
        hard_reasons.append(reason)
        _rule(rules, "R05", "INCUMPLE", reason)
    else:
        _rule(rules, "R05", "CUMPLE", f"{_money(n.amount)} {currency or ''} esta dentro del maximo por factura.")

    committed_before = _committed(records, policy)
    budget: Optional[BudgetSnapshot] = None
    if n.amount is None or currency != policy_currency:
        _rule(rules, "R06", "NO_EVALUABLE", "No se puede calcular el presupuesto con la moneda o el importe actuales.")
    else:
        available_before = policy.period_budget - committed_before
        available_after = available_before - n.amount
        budget = BudgetSnapshot(
            period=policy.period,
            currency=policy_currency,
            configured=policy.period_budget,
            committed_before=committed_before,
            amount=n.amount,
            available_before=available_before,
            available_after=available_after if not hard_reasons and not pending_reasons else available_before,
        )
        if n.amount > available_before:
            reason = f"El presupuesto disponible es {_money(available_before)} y la factura requiere {_money(n.amount)}."
            hard_reasons.append(reason)
            _rule(rules, "R06", "INCUMPLE", reason)
        else:
            _rule(rules, "R06", "CUMPLE", f"{_money(committed_before)} comprometidos + {_money(n.amount)} no supera {_money(policy.period_budget)}.")

    beneficiary_id = n.beneficiary_id.upper() if n.beneficiary_id else None
    if beneficiary_id is None:
        _rule(rules, "R07", "NO_EVALUABLE", "No hay beneficiario para comparar con la lista permitida.")
    elif beneficiary_id not in {x.upper() for x in policy.allowed_beneficiaries}:
        reason = f"{beneficiary_id} no esta en la lista de beneficiarios permitidos."
        pending_reasons.append(reason)
        _rule(rules, "R07", "INCUMPLE", reason)
    else:
        _rule(rules, "R07", "CUMPLE", f"{beneficiary_id} esta permitido por la politica.")

    if n.amount is None:
        _rule(rules, "R08", "NO_EVALUABLE", "No hay importe para comparar con el umbral automatico.")
    elif n.amount > policy.auto_threshold:
        reason = f"{_money(n.amount)} supera el umbral automatico de {_money(policy.auto_threshold)}; requiere aprobacion humana."
        pending_reasons.append(reason)
        _rule(rules, "R08", "INCUMPLE", reason)
    else:
        _rule(rules, "R08", "CUMPLE", f"{_money(n.amount)} no supera el umbral automatico de {_money(policy.auto_threshold)}.")

    if hard_reasons:
        decision = "FRENAR"
        authorization = "AUTOMATICA"
        reasons = list(dict.fromkeys(hard_reasons))
        explanation = "Frenado: " + " ".join(reasons)
    elif pending_reasons:
        decision = "ESCALAR"
        authorization = "PENDIENTE"
        reasons = list(dict.fromkeys(pending_reasons))
        explanation = "Pendiente: " + " ".join(reasons)
    else:
        decision = "PAGAR"
        authorization = "AUTOMATICA"
        reasons = ["Todas las reglas deterministas aplicables se cumplen."]
        explanation = (
            f"Aprobado para pago simulado: {n.beneficiary_id} coincide con el acuerdo y la lista permitida; "
            f"{_money(n.amount or Decimal('0'))} {currency} esta dentro de los limites."
        )

    if budget is not None and decision == "PAGAR":
        budget = budget.model_copy(update={"available_after": budget.available_before - budget.amount})
        explanation += f" Se comprometen {_money(budget.amount)} {budget.currency}; quedan {_money(budget.available_after)} disponibles."
    elif budget is not None and decision != "PAGAR":
        budget = budget.model_copy(update={"available_after": budget.available_before})
        explanation += f" No se compromete presupuesto; el disponible sigue en {_money(budget.available_before)} {budget.currency}."

    _rule(rules, "R09", "CUMPLE" if decision == "PAGAR" else "NO_APLICA", f"Resultado final: {decision}.")
    return DecisionResult(
        decision=decision,
        authorization=authorization,
        policy_version=policy.version,
        period=policy.period,
        rules=rules,
        reasons=reasons,
        explanation=explanation,
        budget=budget,
        evaluated_at=datetime.now(timezone.utc),
    )


class DecisionService:
    def __init__(self, store: IntakeStore, references: ReferenceSource):
        self._store = store
        self._references = references

    def decide(self, intake_id: str) -> Optional[DecisionResult]:
        record = self._store.get(intake_id)
        if record is None:
            return None
        if record.decision is not None:
            return record.decision
        policy, _ = self._references.get_policy()
        decision = evaluate_record(record, policy, self._store.list_all())
        self._store.update_decision(intake_id, decision)
        return decision
