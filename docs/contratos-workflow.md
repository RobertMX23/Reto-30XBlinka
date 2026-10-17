# Contrato versionado del workflow Blinka

**Versión:** `1.0`  
**Propósito:** mantener consistencia entre las fases, los agentes, las tools y la auditoría.

## 1. Contrato de entrada

Todo ingreso debe normalizarse a `InputRequest` antes de llamar a una tool.

| Campo | Tipo | Obligatorio | Regla |
|---|---|---:|---|
| `schema_version` | `string` | Sí | Debe ser `1.0` |
| `request_id` | `string` | No | Se conserva si viene informado |
| `source_type` | enum | Sí después de clasificar | `TEXT`, `TXT_FILE`, `PDF_TEXT`, `PDF_SCAN`, `IMAGE`, `EMAIL`, `EMAIL_ATTACHMENT` |
| `origin` | `string` | Sí | `CHAT`, `UPLOAD`, `EMAIL` o `SYSTEM` |
| `filename` | `string?` | No | Obligatorio para archivos |
| `mime_type` | `string?` | No | Debe ser compatible con `source_type` |
| `path` | `string?` | Condicional | Solo rutas autorizadas |
| `content` | `string?` | Condicional | Obligatorio para texto inline |
| `message_id` | `string?` | Condicional | Obligatorio para correo |
| `ingest_key` | `string?` | Sí al persistir | Idempotencia del ingreso |
| `run_decision` | `bool` | Sí | Por defecto `false` |

Un request no puede proporcionar simultáneamente `path` y `content`. La fuente debe tener exactamente un contenido primario.

## 2. Contrato de salida de cada fase

Cada nodo debe devolver un objeto con esta forma mínima:

```json
{
  "contract_version": "1.0",
  "state": "CLASSIFIED",
  "request": {},
  "intake_id": null,
  "result": {},
  "issues": [],
  "evidence": [],
  "trace": {
    "agent": "classification_agent",
    "tool": "classify_source",
    "timestamp": "2026-10-17T00:00:00Z"
  },
  "moves_money": false
}
```

Reglas obligatorias:

- `state` siempre es un valor del enum de estados.
- `issues` siempre es una lista, aunque esté vacía.
- `evidence` siempre identifica la fuente de la conclusión.
- `moves_money` siempre es `false`.
- Un nodo no debe eliminar datos producidos por una fase anterior.
- Un nodo solo puede agregar datos propios o actualizar el estado según su contrato.

## 3. Contrato de fases

| Fase | Entrada mínima | Salida obligatoria | Estado permitido |
|---|---|---|---|
| Clasificación | `InputRequest` o entrada ADK | `request`, tipo de fuente, incidencias | `CLASSIFIED`, `REJECTED` |
| Preservación | request clasificado | hash, origen, tamaño, fuente original | `PRESERVED`, `FAILED` |
| Extracción | fuente preservada | texto, metadatos, confianza | `EXTRACTED`, `ESCALAR`, `FAILED` |
| Parseo | texto extraído | campos candidatos y normalizados | `PARSED`, `ESCALAR`, `FRENAR` |
| Referencias | campos normalizados | política, beneficiario, acuerdo | `REFERENCES_LOADED`, `ESCALAR` |
| Registro | fuente, extracción y referencias | `intake_id`, recibo, resultado de persistencia | `REGISTERED`, `READY_FOR_DECISION` |
| Decisión | `intake_id` registrado | decisión, reglas, razones, presupuesto | `PAGAR`, `FRENAR`, `ESCALAR` |
| Auditoría | resultado de cualquier fase | evento append-only | estado recibido |

Una fase no puede saltarse una dependencia. Por ejemplo, decisión no puede ejecutarse sin `intake_id` registrado.

## 4. Contrato de decisión

```json
{
  "decision": "PAGAR|FRENAR|ESCALAR",
  "authorization": "AUTOMATICA|HUMANA|PENDIENTE",
  "policy_version": "DEMO-v1",
  "rules": [
    {
      "rule_id": "R01",
      "result": "CUMPLE|INCUMPLE|NO_EVALUABLE|NO_APLICA",
      "evidence": "..."
    }
  ],
  "reasons": ["..."],
  "explanation": "...",
  "evaluated_at": "2026-10-17T00:00:00Z",
  "llm_used": false,
  "moves_money": false
}
```

Precedencia:

1. Si existe incumplimiento duro, el resultado es `FRENAR`.
2. Si no existe incumplimiento duro pero falta información o autorización, el resultado es `ESCALAR`.
3. Solo si todas las reglas aplicables cumplen, el resultado es `PAGAR`.

## 5. Contrato de aprobación humana

Una aprobación humana nunca reemplaza el evento original. Agrega un evento posterior:

```json
{
  "intake_id": "INT-...",
  "previous_state": "ESCALAR",
  "new_state": "HUMAN_APPROVED|HUMAN_REJECTED|NEEDS_MORE_INFORMATION",
  "actor_role": "ANALISTA_CUENTAS_POR_PAGAR|RESPONSABLE_FINANZAS",
  "actor_id": "user-...",
  "comment": "...",
  "created_at": "2026-10-17T00:00:00Z"
}
```

## 6. Contrato de error

```json
{
  "code": "SOURCE_TYPE_UNSUPPORTED",
  "message": "...",
  "retryable": false,
  "phase": "EXTRACTION",
  "details": {}
}
```

Los errores de datos producen `FRENAR` o `ESCALAR`. Los errores técnicos producen `FAILED` y nunca deben convertirse automáticamente en `PAGAR`.

## 7. Contrato de trazabilidad

Cada evento debe registrar:

- `request_id`
- `intake_id`, si ya existe
- `contract_version`
- `agent`
- `tool`
- estado anterior y nuevo
- entrada resumida o hash
- salida resumida
- incidencias
- timestamp

La fuente completa se conserva en almacenamiento; los logs no deben exponer datos sensibles innecesarios.

## 8. Transiciones válidas

```text
RECEIVED -> CLASSIFIED
CLASSIFIED -> PRESERVED | REJECTED
PRESERVED -> EXTRACTING | FAILED
EXTRACTING -> EXTRACTED | ESCALAR | FAILED
EXTRACTED -> PARSED | ESCALAR | FRENAR
PARSED -> REFERENCES_LOADED | ESCALAR | FRENAR
REFERENCES_LOADED -> REGISTERED | ESCALAR | FRENAR
REGISTERED -> READY_FOR_DECISION
READY_FOR_DECISION -> PAGAR | FRENAR | ESCALAR
ESCALAR -> HUMAN_APPROVED | HUMAN_REJECTED | NEEDS_MORE_INFORMATION
PAGAR -> COMPLETED
FRENAR -> COMPLETED
HUMAN_APPROVED -> COMPLETED
HUMAN_REJECTED -> COMPLETED
NEEDS_MORE_INFORMATION -> RECEIVED
FAILED -> FAILED
```

## 9. Compatibilidad

El contrato se implementa en `src/blinka/domain/input_models.py` y debe validarse en cada frontera. Cualquier cambio incompatible requiere incrementar `schema_version`, actualizar las pruebas y documentar la migración.
