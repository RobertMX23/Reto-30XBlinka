"""Nodos del coordinador: delegan en tools y servicios deterministas."""

from __future__ import annotations

from typing import Any

from blinka.domain.input_models import InputIssue, IntentType, OrchestrationResult, WorkflowState
from blinka.domain.batch_models import BatchItem, BatchRequest, BatchResult
from blinka.application.batch import process_batch, process_and_persist_batch
from blinka.adapters.sqlite_batch_store import SqliteBatchStore
from blinka.config import Settings
from blinka.tools.input_tools import classify_input, preserve_input, validate_supported_input
from blinka.wiring import build_service


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"input": value}


def _event(node_input: dict[str, Any], phase: str, state: WorkflowState, **details: Any) -> dict[str, Any]:
    """Añade un evento observable sin registrar contenido sensible completo."""
    event = {"phase": phase, "state": state.value, **details}
    return {**node_input, "events": [*node_input.get("events", []), event]}


def classify_intent(node_input: Any) -> dict[str, Any]:
    """Clasifica la intención sin interpretar ni persistir una factura."""
    raw = node_input.get("input", node_input) if isinstance(node_input, dict) else node_input
    if isinstance(raw, dict):
        if raw.get("source_type") or raw.get("path") or raw.get("content"):
            return {"input": raw, "intent": IntentType.INVOICE}
        return {"input": raw, "intent": IntentType.UNKNOWN}
    if hasattr(raw, "parts"):
        raw = "".join(getattr(part, "text", "") or "" for part in raw.parts)
    text = str(raw or "").strip()
    folded = text.casefold()
    if not text:
        intent = IntentType.UNKNOWN
    elif any(token in folded for token in ("beneficiario:", "importe:", "número de factura:", "numero de factura:", "moneda:")):
        intent = IntentType.INVOICE
    elif any(token in folded for token in ("hola", "buenos días", "buenas tardes", "buenas")):
        intent = IntentType.GREETING
    elif any(token in folded for token in ("estado", "estatus", "cómo va", "como va")):
        intent = IntentType.STATUS_QUERY
    elif "?" in text or any(token in folded for token in ("qué ", "que ", "cómo ", "como ", "explica")):
        intent = IntentType.QUESTION
    else:
        intent = IntentType.UNKNOWN
    return {"input": raw, "intent": intent, "events": [{"phase": "classify_intent", "state": WorkflowState.RECEIVED.value, "intent": intent.value}]}


def classify_source(node_input: Any) -> dict[str, Any]:
    raw = node_input.get("input", node_input) if isinstance(node_input, dict) else node_input
    intent = node_input.get("intent") if isinstance(node_input, dict) else None
    if intent and intent != IntentType.INVOICE:
        response = {
            IntentType.GREETING: "Hola. Puedo revisar una factura, validar sus referencias o consultar un ingreso.",
            IntentType.QUESTION: "Puedo ayudarte con el estado, las reglas o el flujo de una factura.",
            IntentType.STATUS_QUERY: "Para consultar un estado necesito el ID del ingreso o los datos de la factura.",
            IntentType.UNKNOWN: "Necesito una factura o una pregunta relacionada con cuentas por pagar.",
        }[intent]
        return _event({"intent": intent, "state": WorkflowState.COMPLETED, "issues": [], "response": response}, "classify_source", WorkflowState.COMPLETED)
    try:
        request = classify_input(raw)
        issues = validate_supported_input(request)
    except Exception as exc:
        return OrchestrationResult(state=WorkflowState.REJECTED, issues=[InputIssue(code="INVALID_INPUT", message=str(exc))]).model_dump(mode="json")
    return _event({"intent": IntentType.INVOICE, "request": request.model_dump(mode="json"), "state": WorkflowState.CLASSIFIED, "issues": issues}, "classify_source", WorkflowState.CLASSIFIED, issue_count=len(issues))


def ingest_source(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues") or node_input.get("intent") != IntentType.INVOICE:
        return node_input
    request = classify_input(node_input["request"])
    try:
        result = build_service().ingest(preserve_input(request))
    except Exception as exc:
        return {**node_input, "state": WorkflowState.FAILED, "issues": [{"code": "INGEST_FAILED", "message": str(exc), "retryable": False}]}
    receipt = result.receipt.model_dump(mode="json")
    return _event({**node_input, "state": WorkflowState.READY_FOR_DECISION, "intake_id": receipt["intake_id"], "receipt": receipt, "ingest_outcome": result.outcome}, "ingest_source", WorkflowState.READY_FOR_DECISION, outcome=result.outcome)


def evaluate_invoice(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues") or node_input.get("intent") != IntentType.INVOICE:
        return node_input
    try:
        decision = build_service().decide(node_input["intake_id"])
    except Exception as exc:
        return {**node_input, "state": WorkflowState.FAILED, "issues": [{"code": "DECISION_FAILED", "message": str(exc), "retryable": False}]}
    new_state = WorkflowState(decision.decision)
    return _event({**node_input, "state": new_state, "decision": decision.model_dump(mode="json"), "moves_money": False}, "evaluate_invoice", new_state, decision=decision.decision)


evaluate_if_requested = evaluate_invoice


def audit_result(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues"):
        return node_input
    result = OrchestrationResult(
        request_id=node_input.get("request", {}).get("request_id"),
        intent=node_input.get("intent"),
        state=WorkflowState(node_input.get("state", WorkflowState.COMPLETED)),
        source_type=node_input.get("request", {}).get("source_type"),
        intake_id=node_input.get("intake_id"),
        receipt=node_input.get("receipt"),
        decision=node_input.get("decision"),
        events=node_input.get("events", []),
        response=node_input.get("response"),
        moves_money=False,
    )
    return result.model_dump(mode="json")


def process_batch_item(batch_id: str, item: BatchItem) -> BatchItem:
    """Ejecuta un documento del lote por el mismo camino que una entrada individual."""
    request = item.request
    if request.ingest_key is None:
        request = request.model_copy(update={"ingest_key": f"{batch_id}:{item.document_id}"})
    classified_intent = classify_intent(request.model_dump(mode="json"))
    classified = classify_source(classified_intent)
    ingested = ingest_source(classified)
    evaluated = evaluate_invoice(ingested)
    result = audit_result(evaluated)
    state = WorkflowState(result.get("state", WorkflowState.FAILED))
    issues = [InputIssue.model_validate(issue) for issue in result.get("issues", [])]
    return item.model_copy(update={"request": request, "state": state, "result": result, "issues": issues})


def process_batch_request(request: BatchRequest) -> BatchResult:
    """Fan-out/fan-in local del orquestador; el límite lo define BatchRequest."""
    return process_batch(request, lambda item: process_batch_item(request.batch_id, item))


def process_and_persist_batch_request(request: BatchRequest, settings: Settings | None = None) -> BatchResult:
    settings = settings or Settings.from_env()
    store = SqliteBatchStore(settings.db_path)
    return process_and_persist_batch(request, lambda item: process_batch_item(request.batch_id, item), store)
