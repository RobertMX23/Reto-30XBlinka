"""Ejecuta el workflow ADK REAL (InMemoryRunner). Sin credenciales, sin modelo."""

import asyncio
import json

import pytest
from google.adk.runners import InMemoryRunner
from google.genai import types

from agents.blinka_agent.agent import root_agent
from blinka.wiring import build_service
from tests.conftest import REPO

EXPECTED_ORDER = ["read_source", "parse_and_validate", "load_references", "save_intake", "recover_receipt"]


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    for var in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_GENAI_USE_VERTEXAI", "GOOGLE_CLOUD_PROJECT"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("BLINKA_DB_PATH", str(tmp_path / "adk.db"))
    monkeypatch.setenv("BLINKA_ROOT", str(REPO))


def run_workflow(request: dict):
    async def _run():
        runner = InMemoryRunner(agent=root_agent, app_name="blinka-test")
        session = await runner.session_service.create_session(app_name="blinka-test", user_id="t")
        message = types.Content(role="user", parts=[types.Part(text=json.dumps(request))])
        return [e async for e in runner.run_async(user_id="t", session_id=session.id, new_message=message)]

    return asyncio.run(_run())


def node_names(events):
    return [e.node_info.path.split("/")[-1].split("@")[0] for e in events if e.node_info and e.node_info.path]


def test_workflow_is_made_only_of_function_nodes():
    kinds = {type(n).__name__ for n in root_agent.graph.nodes}
    assert kinds <= {"FunctionNode", "BaseNode"}, kinds  # ningun LlmAgent decide los pasos


def test_workflow_traverses_all_steps_and_ends_without_decision():
    events = run_workflow({"path": "data/invoices/factura_completa.txt"})
    assert node_names(events) == EXPECTED_ORDER
    final = events[-1].output
    receipt = final["receipt"]
    assert final["ingest_outcome"] == "CREATED"
    assert receipt["decision"] is None and receipt["llm_used"] is False and receipt["moves_money"] is False
    assert receipt["fields"]["amount"] == "800.00" and receipt["processing_status"] == "REGISTRADA"
    # El recibo viene de la base, no de la memoria del workflow:
    assert build_service().receipt_for(receipt["intake_id"]).model_dump(mode="json") == receipt


def test_workflow_replay_and_conflict():
    request = {"path": "data/invoices/factura_completa.txt", "ingest_key": "K-ADK"}
    first = run_workflow(request)[-1].output
    again = run_workflow(request)[-1].output
    assert (first["ingest_outcome"], again["ingest_outcome"]) == ("CREATED", "REPLAYED")
    assert first["receipt"] == again["receipt"]
    conflict = run_workflow({"path": "data/invoices/factura_sin_vencimiento.txt", "ingest_key": "K-ADK"})[-1].output
    assert conflict["error"]["code"] == "INGEST_CONFLICT" and conflict["error"]["kind"] == "CONFLICT"
    assert build_service().receipt_for(first["receipt"]["intake_id"]).fields["beneficiary_id"] == "PROV-A"  # original intacto


def test_workflow_rejects_path_outside_authorized_directory():
    final = run_workflow({"path": "README.md"})[-1].output
    assert final["error"]["code"] == "PATH_NOT_ALLOWED" and final["error"]["kind"] == "REJECTED"
    assert "receipt" not in final


def test_workflow_with_instruction_in_invoice_has_no_decision():
    receipt = run_workflow({"path": "data/invoices/factura_texto_instruccion.txt"})[-1].output["receipt"]
    assert receipt["decision"] is None and receipt["issues"] == []


def test_workflow_invalid_request_is_a_rejection_not_a_success():
    async def _run():
        runner = InMemoryRunner(agent=root_agent, app_name="blinka-test")
        session = await runner.session_service.create_session(app_name="blinka-test", user_id="t")
        message = types.Content(role="user", parts=[types.Part(text="no soy json")])
        return [e async for e in runner.run_async(user_id="t", session_id=session.id, new_message=message)]

    final = asyncio.run(_run())[-1].output
    assert final["error"]["code"] == "INVALID_REQUEST"
