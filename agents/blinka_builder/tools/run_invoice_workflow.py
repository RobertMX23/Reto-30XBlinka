"""Puente entre Visual Builder y el workflow determinista existente."""

from __future__ import annotations

from agents.blinka_orchestrator.nodes import (
    audit_result,
    classify_intent,
    classify_source,
    evaluate_invoice,
    ingest_source,
)


def run_invoice_workflow(invoice_text: str) -> dict:
    """Procesa una factura sin ejecutar instrucciones del documento.

    El Builder controla la conversación; las reglas y la decisión permanecen
    en el mismo código determinista usado por el agente original.
    """
    classified_intent = classify_intent(invoice_text)
    classified = classify_source(classified_intent)
    ingested = ingest_source(classified)
    evaluated = evaluate_invoice(ingested)
    return audit_result(evaluated)
