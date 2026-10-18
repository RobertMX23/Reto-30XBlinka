import pytest
from blinka.adapters.in_memory_store import InMemoryFactStore
from blinka.application.memory_projection import project_invoice_to_memory


def _receipt(number="F-1"):
    return {"intake_id": "INT-1", "fields": {"invoice_number": number, "beneficiary_id": "PROV-A", "amount": "800.00", "currency": "USD"}}


def test_memory_search_isolated_by_tenant():
    store = InMemoryFactStore()
    store.add_fact(project_invoice_to_memory(_receipt(), {"decision": "PAGAR"}, tenant_id="acme"))
    store.add_fact(project_invoice_to_memory(_receipt("F-2"), {"decision": "FRENAR"}, tenant_id="other"))
    result = store.search({"query": "PROV-A", "tenant_id": "acme", "top_k": 5})
    assert len(result.memories) == 1
    assert result.authoritative is False
    assert result.moves_money is False


def test_memory_rejects_untrusted_or_money_fact():
    store = InMemoryFactStore()
    fact = project_invoice_to_memory(_receipt(), tenant_id="acme")
    with pytest.raises(ValueError):
        store.add_fact(fact.model_copy(update={"moves_money": True}))
