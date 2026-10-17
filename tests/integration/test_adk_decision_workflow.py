"""Ejecuta el workflow ADK F2 real de comparacion y decision."""

import asyncio
import json

from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.blinka_agent.decision_agent import root_agent
from tests.conftest import REPO, make_service


def _run(intake_id: str):
    async def _inner():
        runner = InMemoryRunner(agent=root_agent, app_name="blinka-decision-test")
        session = await runner.session_service.create_session(app_name="blinka-decision-test", user_id="t")
        message = types.Content(role="user", parts=[types.Part(text=json.dumps({"intake_id": intake_id}))])
        return [event async for event in runner.run_async(user_id="t", session_id=session.id, new_message=message)]

    return asyncio.run(_inner())


def test_decision_workflow_persists_explainable_result(settings, monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("BLINKA_DB_PATH", str(settings.db_path))
    monkeypatch.setenv("BLINKA_ROOT", str(REPO))
    service = make_service(settings)
    intake = service.ingest({"text": "\n".join([
        "Beneficiario: PROV-A",
        "Número de factura: ADK-F2-001",
        "Importe: 800.00",
        "Moneda: USD",
        "Vencimiento: 2026-10-30",
        "Acuerdo: AC-A-001",
    ]), "ingest_key": "adk-f2-001"})

    events = _run(intake.receipt.intake_id)
    final = events[-1].output

    assert final["decision"]["decision"] == "PAGAR"
    assert final["decision"]["moves_money"] is False
    assert final["receipt"]["decision"]["explanation"].startswith("Aprobado para pago simulado")

