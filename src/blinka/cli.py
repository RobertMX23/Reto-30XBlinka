"""CLI local: inicializar, ingresar una factura y consultar un ingreso. Sin credenciales ni red.

    python -m blinka.cli init [--reset]
    python -m blinka.cli ingest data/invoices/factura_completa.txt [--key CLAVE] [--adk]
    python -m blinka.cli ingest --text "Beneficiario: PROV-A ..." 
    python -m blinka.cli decide INT-XXXXXXXXXXXX
    python -m blinka.cli show INT-XXXXXXXXXXXX [--source]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Optional, Sequence

from blinka.adapters.reference_files import JsonReferenceSource
from blinka.config import Settings
from blinka.errors import BlinkaError, IngestConflictError
from blinka.wiring import build_service

EXIT_BY_KIND = {"TECHNICAL": 1, "REJECTED": 2, "CONFLICT": 3}


def _print(obj: Any) -> None:
    print(json.dumps(obj, ensure_ascii=False, indent=2, default=str))


def _error_payload(exc: BlinkaError) -> dict:
    payload = {"code": exc.code, "kind": exc.kind, "message": str(exc)}
    if isinstance(exc, IngestConflictError):
        payload.update(intake_id=exc.intake_id, existing_sha256=exc.existing_sha256, new_sha256=exc.new_sha256)
    return payload


def run_with_adk(request: dict) -> dict:
    """Ejecuta el MISMO recorrido a traves del workflow ADK (funciones, sin modelo). Devuelve la salida final."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    import importlib

    root = Settings.from_env().root
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    agent_module = importlib.import_module("agents.blinka_agent.agent")

    async def _run() -> dict:
        runner = InMemoryRunner(agent=agent_module.root_agent, app_name="blinka")
        session = await runner.session_service.create_session(app_name="blinka", user_id="cli")
        message = types.Content(role="user", parts=[types.Part(text=json.dumps(request))])
        last: Optional[dict] = None
        async for event in runner.run_async(user_id="cli", session_id=session.id, new_message=message):
            if getattr(event, "output", None) is not None:
                last = event.output
        return last or {"error": {"code": "NO_OUTPUT", "kind": "TECHNICAL", "message": "El workflow no produjo salida."}}

    return asyncio.run(_run())


def run_decision_with_adk(intake_id: str) -> dict:
    """Ejecuta el recorrido F2 a traves de un workflow ADK de funciones."""
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    import importlib

    root = Settings.from_env().root
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    agent_module = importlib.import_module("agents.blinka_agent.decision_agent")

    async def _run() -> dict:
        runner = InMemoryRunner(agent=agent_module.root_agent, app_name="blinka")
        session = await runner.session_service.create_session(app_name="blinka", user_id="cli")
        message = types.Content(role="user", parts=[types.Part(text=json.dumps({"intake_id": intake_id}))])
        last: Optional[dict] = None
        async for event in runner.run_async(user_id="cli", session_id=session.id, new_message=message):
            if getattr(event, "output", None) is not None:
                last = event.output
        return last or {"error": {"code": "NO_OUTPUT", "kind": "TECHNICAL", "message": "El workflow no produjo salida."}}

    return asyncio.run(_run())


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="blinka", description="Blinka F0/F1/F2: ingreso y decision simulada de facturas sinteticas.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="Crea la base local y valida las referencias ficticias.")
    p_init.add_argument("--reset", action="store_true", help="Borra SOLO la base local configurada antes de crearla.")

    p_ing = sub.add_parser("ingest", help="Ingresa una factura sintetica.")
    p_ing.add_argument("path", nargs="?", help="Ruta dentro del directorio de facturas autorizado.")
    p_ing.add_argument("--text", help="Texto de prueba en lugar de una ruta.")
    p_ing.add_argument("--key", help="Clave de ingreso (idempotencia). Por defecto, se deriva de la ruta o del contenido.")
    p_ing.add_argument("--adk", action="store_true", help="Ejecutar a traves del workflow ADK.")

    p_show = sub.add_parser("show", help="Consulta un ingreso por ID.")
    p_show.add_argument("intake_id")
    p_show.add_argument("--source", action="store_true", help="Incluye el texto original conservado.")

    p_decide = sub.add_parser("decide", help="Evalua y registra una decision F2 sin mover dinero.")
    p_decide.add_argument("intake_id")
    p_decide.add_argument("--adk", action="store_true", help="Ejecutar la decision a traves del workflow ADK.")

    args = parser.parse_args(argv)
    settings = Settings.from_env()

    try:
        if args.cmd == "init":
            if args.reset and settings.db_path.exists():
                settings.db_path.unlink()
            service = build_service(settings)
            refs = JsonReferenceSource(settings.reference_dir).summary()
            invoices = sorted(p.name for p in settings.invoices_dir.glob("*.txt"))
            _print({"database": str(settings.db_path), "references": refs, "invoices_available": invoices, "moves_money": False})
            return 0

        if args.cmd == "ingest":
            if (args.path is None) == (args.text is None):
                parser.error("indica exactamente uno: PATH o --text")
            request = {"path": args.path} if args.path else {"text": args.text}
            if args.key:
                request["ingest_key"] = args.key
            if args.adk:
                out = run_with_adk(request)
                _print(out)
                return EXIT_BY_KIND.get(out.get("error", {}).get("kind"), 0) if "error" in out else 0
            result = build_service(settings).ingest(request)
            _print({"ingest_outcome": result.outcome, "receipt": result.receipt.model_dump(mode="json")})
            return 0

        if args.cmd == "show":
            service = build_service(settings)
            record = service.get_record(args.intake_id)
            if record is None:
                _print({"error": {"code": "NOT_FOUND", "kind": "REJECTED", "message": f"No existe {args.intake_id}"}})
                return 2
            from blinka.application.intake import build_receipt

            payload = {"receipt": build_receipt(record).model_dump(mode="json")}
            if args.source:
                payload["source_text"] = record.source.text
            _print(payload)
            return 0

        if args.cmd == "decide":
            if args.adk:
                out = run_decision_with_adk(args.intake_id)
                _print(out)
                return EXIT_BY_KIND.get(out.get("error", {}).get("kind"), 0) if "error" in out else 0
            service = build_service(settings)
            decision = service.decide(args.intake_id)
            if decision is None:
                _print({"error": {"code": "NOT_FOUND", "kind": "REJECTED", "message": f"No existe {args.intake_id}"}})
                return 2
            receipt = service.receipt_for(args.intake_id)
            _print({"decision": decision.model_dump(mode="json"), "receipt": receipt.model_dump(mode="json") if receipt else None})
            return 0
    except BlinkaError as exc:
        _print({"error": _error_payload(exc)})
        return EXIT_BY_KIND.get(exc.kind, 1)
    return 0  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
