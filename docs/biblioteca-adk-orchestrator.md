# Biblioteca ADK y plan de mejora de `blinka_orchestrator`

Este documento clasifica las referencias oficiales de ADK que gobiernan el diseño del orquestador. Las tareas deben ejecutarse en orden; cada una consume el artefacto y el contrato de la anterior.

## 1. Biblioteca de referencias

| Área | Referencias | Uso en Blinka | Fase |
|---|---|---|---|
| Runtime | [RunConfig](https://adk.dev/runtime/runconfig/), [event loop](https://adk.dev/runtime/event-loop/) | Límites de ejecución, sesiones, streaming y contexto | T1, T8 |
| Observabilidad | [logging](https://adk.dev/observability/logging/), [metrics](https://adk.dev/observability/metrics/), [traces](https://adk.dev/observability/traces/) | Evidencia por fase, latencia, errores y decisiones | T2 |
| Evaluación | [criteria](https://adk.dev/evaluate/criteria/), [user simulation](https://adk.dev/evaluate/user-sim/), [environment simulation](https://adk.dev/evaluate/environment_simulation/), [custom metrics](https://adk.dev/evaluate/custom_metrics/) | Casos de aceptación y métricas de seguridad | T6, T7 |
| Optimización | [optimize](https://adk.dev/optimize/) | Mejorar calidad y costo después de tener mediciones | T9 |
| Tools | [multi-tool agent](https://adk.dev/tutorials/multi-tool-agent/) | Tools deterministas para entrada, referencias, reglas y auditoría | T3 |
| Equipos | [agent team](https://adk.dev/tutorials/agent-team/), [collaboration](https://adk.dev/workflows/collaboration/) | Delegación entre agentes cuando exista una responsabilidad aislada | T5 |
| Agentes con modelo | [LLM agents](https://adk.dev/agents/llm-agents/), [managed agents](https://adk.dev/agents/managed-agents/) | Intención y extracción asistida; nunca autoridad sobre la decisión | T4 |
| Rutas | [graph routes](https://adk.dev/graphs/routes/), [routing](https://adk.dev/agents/routing/) | Elegir saludo, consulta, factura, correo o revisión | T4 |
| Workflows | [workflows](https://adk.dev/workflows/), [workflow agents](https://adk.dev/agents/workflow-agents/), [sequential](https://adk.dev/agents/workflow-agents/sequential-agents/), [loop](https://adk.dev/agents/workflow-agents/loop-agents/), [parallel](https://adk.dev/agents/workflow-agents/parallel-agents/) | Pipeline determinista y futuras fases paralelas | T3, T5 |
| Workflows personalizados | [custom agents](https://adk.dev/agents/custom-agents/), [patterns](https://adk.dev/workflows/patterns/), [dynamic](https://adk.dev/graphs/dynamic/) | Estados y rutas condicionadas | T5 |
| Datos y estado | [data handling](https://adk.dev/graphs/data-handling/) | Contrato de datos entre nodos y persistencia | T1, T3 |
| Persona | [human input](https://adk.dev/graphs/human-input/) | Resolver `ESCALAR` sin saltar reglas | T10 |
| Tutoriales | [tutorials](https://adk.dev/tutorials/) | Ejemplos de referencia, no contratos de negocio | Todas |

## 2. Secuencia de tareas interconectadas

| ID | Tarea | Depende de | Artefacto | Contrato | Resultado esperado |
|---|---|---|---|---|---|
| T1 | Congelar contrato de ejecución y datos | — | `docs/contratos-workflow.md` | `InputRequest`, `OrchestrationResult`, `WorkflowState` | Todos los nodos intercambian la misma forma versionada |
| T2 | Instrumentar observabilidad | T1 | `docs/observabilidad-orchestrator.md` + eventos | Evento con `request_id`, fase, tool, estado y duración | Cada ejecución permite explicar dónde y por qué terminó |
| T3 | Formalizar tools deterministas | T1 | `src/blinka/tools/` | Entrada/salida tipada, sin efectos ocultos | El orquestador coordina tools, no lógica duplicada |
| T4 | Incorporar routing de intención | T1, T3 | `intent_agent` o `classify_intent` | `IntentResult` con intención, confianza y aclaración | Saludos/preguntas no crean facturas; facturas entran al intake |
| T5 | Componer agentes especializados | T2, T3, T4 | `agents/` + workflow | Cada agente tiene una responsabilidad única | Flujo trazable: intención, fuente, extracción, referencias, decisión, auditoría |
| T6 | Crear matriz de evaluación | T1, T4, T5 | `tests/evals/` y dataset sintético | Entrada, expectativa, criterios y evidencia | Casos `PAGAR`, `FRENAR`, `ESCALAR` reproducibles |
| T7 | Métricas de seguridad y calidad | T2, T6 | reporte de métricas | `wrong_auto_pay == 0`, cobertura y latencia | Se mide seguridad antes de optimizar |
| T8 | Configurar runtime | T2, T5 | configuración de runner | `RunConfig` con límites explícitos | Ejecuciones reproducibles y acotadas |
| T9 | Optimizar | T7, T8 | reporte comparativo | Cambios medidos contra línea base | Mejoras sin perder seguridad ni trazabilidad |
| T10 | Human-in-the-loop | T5, T6 | contrato de aprobación y estado | actor, alcance, comentario, timestamp | `ESCALAR` espera y revalida; no se convierte automáticamente en `PAGAR` |

## 3. Contrato operativo de T1

Cada nodo recibe y devuelve un payload versionado:

```json
{
  "contract_version": "1.0",
  "request_id": "REQ-...",
  "intent": "INVOICE",
  "state": "CLASSIFIED",
  "request": {},
  "result": {},
  "issues": [],
  "events": [],
  "moves_money": false
}
```

Invariantes:

- Un nodo no elimina datos de fases anteriores.
- `moves_money` siempre es `false`.
- Una decisión de negocio solo ocurre con un `intake_id` registrado.
- `PAGAR` requiere todas las reglas aplicables en `CUMPLE`.
- `ESCALAR` requiere razón y siguiente acción humana.
- `FRENAR` requiere evidencia del incumplimiento duro.
- Los errores técnicos no se convierten en aprobaciones.

## 4. Primera implementación iniciada

La base actual ya cubre parte de T1 y T4:

```text
classify_intent
→ classify_source
→ ingest_source
→ evaluate_invoice
→ audit_result
```

La siguiente edición de código debe completar T2 y T3 antes de introducir un `LlmAgent`: primero eventos y tools observables, después routing semántico y finalmente delegación entre agentes.

## 5. Criterio de avance

Una tarea se considera completa solo cuando:

1. El artefacto está versionado.
2. El contrato está validado.
3. Existe una prueba positiva y una negativa.
4. La suite existente sigue pasando.
5. El resultado aparece en ADK mediante eventos o trazas.

La evaluación debe medir el comportamiento del sistema, no la apariencia del diagrama.
