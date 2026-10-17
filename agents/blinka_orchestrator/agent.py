"""Punto de entrada del coordinador ADK para la ingesta y decisión opcional."""

from google.adk import Workflow

from . import nodes

root_agent = Workflow(
    name="blinka_orchestrator",
    edges=[("START", nodes.classify_source, nodes.ingest_source, nodes.evaluate_if_requested, nodes.audit_result)],
)
