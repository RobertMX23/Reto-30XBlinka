"""Pruebas del coordinador multiagente y sus contratos deterministas."""

import asyncio
import json

from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.blinka_orchestrator.agent import root_agent

from agents.blinka_orchestrator import nodes
from blinka.domain.input_models import WorkflowState


def _invoice():
    return "\n".join([
        "Beneficiario: PROV-A",
        "Numero de factura: ORCH-001",
        "Importe: 800.00",
        "Moneda: USD",
        "Vencimiento: 2026-10-25",
        "Acuerdo: AC-A-001",
    ])


def test_orchestrator_happy_path_registers_text(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))
    classified = nodes.classify_source({"content": _invoice(), "origin": "CHAT"})
    assert classified["state"] == WorkflowState.CLASSIFIED
    assert classified["request"]["source_type"] == "TEXT"
    ingested = nodes.ingest_source(classified)
    assert ingested["state"] == WorkflowState.READY_FOR_DECISION
    assert ingested["receipt"]["fields"]["invoice_number"] == "ORCH-001"


def test_orchestrator_does_not_ingest_greeting(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))
    classified = nodes.classify_source(nodes.classify_intent("hola"))
    result = nodes.audit_result(nodes.evaluate_invoice(nodes.ingest_source(classified)))
    assert result["state"] == "COMPLETED"
    assert result["intent"] == "GREETING"
    assert result["intake_id"] is None
    assert "Puedo revisar" in result["response"]


def test_orchestrator_can_chain_deterministic_decision(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))
    classified = nodes.classify_source({"content": _invoice(), "origin": "CHAT", "run_decision": True})
    result = nodes.audit_result(nodes.evaluate_if_requested(nodes.ingest_source(classified)))
    assert result["state"] == "PAGAR"
    assert result["decision"]["moves_money"] is False


def test_orchestrator_requires_path_for_pdf_text():
    result = nodes.classify_source({"source_type": "PDF_TEXT", "filename": "invoice.pdf"})
    assert result["state"] == WorkflowState.CLASSIFIED
    assert result["issues"][0]["code"] == "PATH_REQUIRED"


def test_orchestrator_rejects_unimplemented_scanned_pdf():
    result = nodes.classify_source({"source_type": "PDF_SCAN", "path": "invoice.pdf"})
    assert result["state"] == WorkflowState.CLASSIFIED
    assert result["issues"][0]["code"] == "SOURCE_TYPE_UNSUPPORTED"


def test_orchestrator_adk_workflow_runs_from_plain_user_message(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))

    async def run():
        runner = InMemoryRunner(agent=root_agent, app_name="blinka-orchestrator-test")
        session = await runner.session_service.create_session(app_name="blinka-orchestrator-test", user_id="test")
        message = types.Content(role="user", parts=[types.Part(text=_invoice())])
        return [event async for event in runner.run_async(user_id="test", session_id=session.id, new_message=message)]

    events = asyncio.run(run())
    final = events[-1].output
    assert final["state"] == "READY_FOR_DECISION"
    assert final["receipt"]["fields"]["invoice_number"] == "ORCH-001"


def test_orchestrator_adk_workflow_runs_decision_when_requested(service, monkeypatch):
    monkeypatch.setenv("BLINKA_DB_PATH", str(service._settings.db_path))

    async def run():
        runner = InMemoryRunner(agent=root_agent, app_name="blinka-orchestrator-decision-test")
        session = await runner.session_service.create_session(app_name="blinka-orchestrator-decision-test", user_id="test")
        request = {"content": _invoice(), "origin": "CHAT", "run_decision": True}
        message = types.Content(role="user", parts=[types.Part(text=json.dumps(request))])
        return [event async for event in runner.run_async(user_id="test", session_id=session.id, new_message=message)]

    final = asyncio.run(run())[-1].output
    assert final["state"] == "PAGAR"
    assert final["decision"]["moves_money"] is False
