"""Punto de entrada del coordinador ADK para clasificar y procesar entradas."""

from google.adk import Workflow

from . import nodes

root_agent = Workflow(
    name="blinka_orchestrator",
    edges=[("START", nodes.classify_intent, nodes.classify_source, nodes.ingest_source, nodes.evaluate_invoice, nodes.audit_result)],
)
