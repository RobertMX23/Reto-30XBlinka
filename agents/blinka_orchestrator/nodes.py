"""Nodos del coordinador: delegan en tools y servicios deterministas."""

from __future__ import annotations

from typing import Any

from blinka.domain.input_models import InputIssue, OrchestrationResult, WorkflowState
from blinka.tools.input_tools import classify_input, preserve_input, validate_supported_input
from blinka.wiring import build_service


def _as_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"input": value}


def classify_source(node_input: Any) -> dict[str, Any]:
    raw = node_input.get("input", node_input) if isinstance(node_input, dict) else node_input
    try:
        request = classify_input(raw)
        issues = validate_supported_input(request)
    except Exception as exc:
        return OrchestrationResult(state=WorkflowState.REJECTED, issues=[InputIssue(code="INVALID_INPUT", message=str(exc))]).model_dump(mode="json")
    return {"request": request.model_dump(mode="json"), "state": WorkflowState.CLASSIFIED, "issues": issues}


def ingest_source(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues"):
        return node_input
    request = classify_input(node_input["request"])
    try:
        result = build_service().ingest(preserve_input(request))
    except Exception as exc:
        return {**node_input, "state": WorkflowState.FAILED, "issues": [{"code": "INGEST_FAILED", "message": str(exc), "retryable": False}]}
    receipt = result.receipt.model_dump(mode="json")
    return {**node_input, "state": WorkflowState.READY_FOR_DECISION, "intake_id": receipt["intake_id"], "receipt": receipt, "ingest_outcome": result.outcome}


def evaluate_if_requested(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues") or not node_input.get("request", {}).get("run_decision"):
        return node_input
    try:
        decision = build_service().decide(node_input["intake_id"])
    except Exception as exc:
        return {**node_input, "state": WorkflowState.FAILED, "issues": [{"code": "DECISION_FAILED", "message": str(exc), "retryable": False}]}
    return {**node_input, "state": WorkflowState(decision.decision), "decision": decision.model_dump(mode="json"), "moves_money": False}


def audit_result(node_input: dict[str, Any]) -> dict[str, Any]:
    if node_input.get("issues"):
        return node_input
    result = OrchestrationResult(
        request_id=node_input.get("request", {}).get("request_id"),
        state=WorkflowState(node_input.get("state", WorkflowState.COMPLETED)),
        source_type=node_input.get("request", {}).get("source_type"),
        intake_id=node_input.get("intake_id"),
        receipt=node_input.get("receipt"),
        decision=node_input.get("decision"),
        moves_money=False,
    )
    return result.model_dump(mode="json")
