"""Punto de entrada ADK: `root_agent` es un Workflow de FUNCIONES. No hay LlmAgent ni llamadas a un modelo (F1)."""

from google.adk import Workflow

from . import nodes

root_agent = Workflow(
    name="blinka_intake",
    edges=[
        (
            "START",
            nodes.read_source,
            nodes.parse_and_validate,
            nodes.load_references,
            nodes.save_intake,
            nodes.recover_receipt,
        )
    ],
)
