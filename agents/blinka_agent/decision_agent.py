"""Workflow ADK F2: compara y decide con funciones deterministas, sin LLM."""

from google.adk import Workflow

from . import nodes


root_agent = Workflow(
    name="blinka_decision",
    edges=[("START", nodes.evaluate_decision, nodes.recover_decision)],
)

