from blinka.adapters.in_memory_store import InMemoryFactStore
from blinka.application.memory_projection import project_invoice_to_memory
from blinka.tools.memory_tools import search_blinka_memory


def test_memory_tool_returns_non_authoritative_structured_context():
    store = InMemoryFactStore()
    store.add_fact(project_invoice_to_memory({"intake_id": "I-1", "fields": {"invoice_number": "F-1", "amount": "800.00"}}, tenant_id="acme"))
    result = search_blinka_memory("F-1", "acme", store)
    assert result["authoritative"] is False
    assert result["moves_money"] is False
    assert result["memories"][0]["content"]["invoice_number"] == "F-1"
