# Reto 30X Blinka — Arquitectura en GCP con ADK 2.0

> **Documento:** `BLINKA-README-005` · **Versión:** `0.1.0` · **Estado:** `DRAFT` · **Fecha:** `2026-10-17`
> **Basado en:** `README (2).md` (001), `README (3).md` (003), `README (4).md` (004)
> **Propósito:** decidir dónde y cómo corre el agente en línea (Google Cloud, ADK 2.0, Python), definir el contrato de API, el modelo de datos y las **correcciones** que ADK 2.0 impone al diseño previo.
> **Fuentes consultadas (2026-10-17):** [ADK 2.0](https://adk.dev/2.0/) · [Deploy to Agent Runtime](https://adk.dev/deploy/agent-runtime/index.md) · [ADK para TypeScript](https://developers.googleblog.com/introducing-agent-development-kit-for-typescript-build-ai-agents-with-the-power-of-a-code-first-approach/)

> **Nota de vigencia (2026-10-17):** este documento es un antecedente. La fuente vigente es `docs/` (ver `docs/reto-blinka-fases-adk.md`).
> Corrección: la sección 9 y R-01 afirman que BigQuery no es transaccional; **es incorrecto**, BigQuery sí tiene transacciones.
> El almacén operativo previsto es SQLite (local) y Firestore (nube); BigQuery y Drive son opcionales. Estado real: ver `docs/registro-madurez.md`.

---

## 1. Decisión de stack

| Capa | Decisión | Estado | Razón |
|---|---|---|---|
| Framework de agente | **ADK 2.0** | PROPUESTA | Motor de workflows basado en grafos: agentes, herramientas y funciones son nodos con enrutamiento determinístico. Encaja con "la IA interpreta, las reglas autorizan" |
| Lenguaje | **Python** | PROPUESTA | La documentación de despliegue en Agent Runtime cubre Python y Go; no menciona TypeScript. El motor de reglas es lógica pura, fácil de probar |
| Modelo | Gemini (salida estructurada) | PROPUESTA | Sólo en extracción y redacción; nunca en la decisión |
| Ejecución del agente | **Agent Runtime** (Google Cloud Agent Platform) | PROPUESTA, **por verificar** | Infraestructura gestionada. Alternativa de respaldo: Cloud Run |
| API y pantalla | **Cloud Run** | PROPUESTA | Contenedor propio para API de negocio y UI simple |
| Entrada de facturas | **Google Drive** (carpeta `inbox`) | PROPUESTA | Simula el canal de recepción (§02 del reto) |
| Datos y auditoría | **BigQuery** | PROPUESTA | Políticas versionadas, padrón, acuerdos y registro append-only |
| Cuenta | Proyecto GCP propio, pay-as-you-go | Dado | Con alerta de presupuesto obligatoria |

Esto reemplaza la tabla "TBD" de `README (2).md` §11.

---

## 2. Correcciones por ADK 2.0

Cada fila es un cambio al diseño anterior o una regla de implementación derivada del comportamiento documentado de ADK 2.0.

### 2.1 Correcciones al diseño previo

| # | Documento afectado | Decía | Corrección | Motivo |
|---|---|---|---|---|
| C1 | README 2 §8 "Decision Router" y §7 flujo | Componentes lógicos separados | Se implementan como **nodos de un grafo** de ADK 2.0 (sección 3) | 2.0 sustituye el ejecutor jerárquico por el Workflow Runtime |
| C2 | README 2 §8 "Human Approval" | Componente aparte, mecanismo no definido | `ESCALATE` es una **pausa Human-in-the-Loop** del workflow; la persona la reanuda por API | Las notas de migración de 2.0 describen pausas HITL |
| C3 | README 2 §11 | Stack: TBD | Stack decidido (sección 1) | Decisión de este documento |
| C4 | README 3 §1–2 | El agente "decide" en los pasos 5–6 | El **LLM no participa** en los pasos de regla y decisión: sólo extracción (paso 1) y redacción (paso 7). Reglas y router son nodos de código | RNF-006 y principio rector |
| C5 | README 3 §5 R2, R3 y README 4 §06 | Duplicado y beneficiario nuevo | Se nombran **controles de regla**, no detección de fraude | §06 del reto excluye cumplimiento y fraude |
| C6 | README 4 B3 paso 9 | "Resolución humana" como paso lineal | Es la **reanudación** de la pausa HITL de C2; genera segunda entrada de registro con `actor=humano` | Coherencia con ADK 2.0 |
| C7 | README 2 §12 estructura | Árbol sin infraestructura | Se añaden `infra/`, `api/` y `agent/` (sección 8) | Despliegue en línea |

### 2.2 Reglas de implementación derivadas de los cambios de ADK 2.0

| # | Cambio en ADK 2.0 (1.x → 2.0) | Regla para este proyecto |
|---|---|---|
| A1 | `BaseAgent` ahora es subclase de `BaseNode`; los overrides de `_run_async_impl()` **se omiten** | No sobrescribir `_run_async_impl()`. La lógica de ciclo de vida va en los callbacks before/after del agente |
| A2 | No añadir eventos directamente a la sesión | Los nodos **emiten (yield)** eventos. Ningún nodo escribe en la sesión por su cuenta |
| A3 | Evitar `except` amplios; nunca capturar `BaseException`, porque oculta fallos a los reintentos automáticos y **rompe las pausas HITL** | Prohibido `except:` y `except BaseException`. Los errores esperados se capturan por tipo concreto. **Un fallo no capturado nunca debe terminar en `APPROVE`** |
| A4 | El esquema de Event añade `node_info` y `output` | La tabla de auditoría **no** copia el esquema de Event en columnas rígidas: guarda el evento completo en una columna `JSON` y columnas propias (sección 5) |
| A5 | En TypeScript, `SequentialAgent`, `ParallelAgent` y `LoopAgent` están deprecados a favor de workflows de grafo | Aunque usamos Python, se diseña con **grafo**, no con agentes secuenciales anidados |
| A6 | Despliegue Python en Agent Runtime excluye las librerías del servidor de API y la UI web de ADK | No depender de `adk web` ni del servidor local en producción. La API de negocio vive en Cloud Run |
| A7 | Usar dependencias declaradas | `requirements` fijadas con versión; el paquete desplegado incluye sólo lo declarado |

---

## 3. Grafo del workflow

```
inbox (Drive) ─▶ [1 extract (LLM)] ─▶ [2 normalize] ─▶ [3 lookup (BigQuery)]
                                                              │
                                                              ▼
                                                     [4 policy_engine]   ← código puro, sin LLM
                                                              │
                                                              ▼
                                                        [5 router]
                                      ┌───────────────┬───────┴────────┐
                                      ▼               ▼                ▼
                                   APPROVE          BLOCK          ESCALATE
                                      │               │                │
                                      │               │        [pausa HITL] ◀── POST /decisions/{id}/resolve
                                      └───────┬───────┴────────┬───────┘
                                              ▼                ▼
                                       [6 explain]  ─▶  [7 audit_write (BigQuery)]
```

| Nodo | Tipo | Entrada | Salida | ¿Usa LLM? |
|---|---|---|---|---|
| extract | Agente con salida estructurada | Texto o PDF | beneficiario, monto, moneda, vencimiento, nº de factura (`null` si falta) | **Sí** |
| normalize | Función | Campos extraídos | Campos normalizados (ISO-4217, ISO-8601, decimal) | No |
| lookup | Función | Beneficiario, periodo | Padrón, acuerdo, acumulado del mes, facturas previas | No |
| policy_engine | Función | Campos + referencia + política vigente | Lista de reglas evaluadas (R1–R8, pasó/falló) | **Nunca** |
| router | Función | Resultado de reglas | `APPROVE` / `BLOCK` / `ESCALATE` con precedencia `BLOCK > ESCALATE > APPROVE` | **Nunca** |
| hitl | Pausa | Caso escalado | Decisión humana (aprobar / rechazar) | No |
| explain | Agente restringido | Hechos de las reglas | Texto en lenguaje natural; **no puede cambiar la decisión** | Sí (redacta) |
| audit_write | Función | Todo lo anterior | Fila en BigQuery con snapshot de política | No |

**Garantía de seguridad (por construcción):** el único valor que puede producir `APPROVE` es el nodo `router`, a partir del resultado de `policy_engine`, o la reanudación humana del nodo `hitl`. Los nodos con LLM no tienen la decisión como parámetro escribible. Si `policy_engine` lanza una excepción, el router recibe `NO_EVALUABLE` y el resultado es `ESCALATE`.

---

## 4. Contrato de API (Cloud Run)

Todos los endpoints requieren autenticación (sección 7). Respuestas en JSON.

| Método y ruta | Función | Cuerpo / parámetros | Respuesta |
|---|---|---|---|
| `POST /invoices` | Evaluar una factura | `{ "drive_file_id": "..." }` o `{ "text": "..." }` | Decisión según `README (3).md` §7 + `invoice_number`, `rules_snapshot_id`, `actor` |
| `POST /evaluate-batch` | Evaluar el dataset | `{ "dataset": "synthetic-v1" }` | Resumen + decisiones, procesadas **en serie** |
| `GET /decisions` | Listar | `?status=APPROVE\|BLOCK\|ESCALATE\|PENDING` | Lista paginada |
| `GET /decisions/{id}` | Detalle | — | Extracción, reglas evaluadas, explicación, snapshot |
| `POST /decisions/{id}/resolve` | Resolver un escalado | `{ "resolution": "approve\|reject", "reason": "..." }` | Entrada nueva con `actor=humano` |
| `GET /policies` | Política vigente | — | Valores y `version_id` |
| `PUT /policies` | Editar reglas | Valores nuevos | Nueva versión; la anterior se conserva |
| `GET /metrics` | Métricas de §10 | `?dataset=synthetic-v1` | Autonomía, seguridad, escalado correcto, exactitud |

**Restricción:** `PUT /policies` sólo se alcanza desde la API con identidad humana. Ninguna herramienta del agente expone escritura de políticas (RNF-006).

---

## 5. Modelo de datos (BigQuery)

Dataset `blinka_ap`. Todos los datos son sintéticos.

| Tabla | Tipo | Campos clave |
|---|---|---|
| `policies` | Versionada, append-only | `version_id`, `created_at`, `created_by`, `per_invoice_limit`, `human_threshold`, `monthly_budget`, `reference_currency`, `r4_tolerance_pct`, `config_json` |
| `beneficiaries` | Catálogo | `beneficiary_id`, `name_normalized`, `country`, `type` (equipo/proveedor/contratista), `allowed`, `agreed_currency` |
| `agreements` | Catálogo | `beneficiary_id`, `agreed_amount`, `agreed_currency`, `valid_from`, `valid_to` |
| `invoices` | Entrada | `invoice_id`, `invoice_number`, `source` (drive/text), `drive_file_id`, `received_at`, `raw_text` |
| `decisions` | **Registro append-only** | `decision_id`, `invoice_id`, `actor` (agente/humano), `decision`, `rules_evaluated` (JSON), `explanation`, `rules_snapshot_id`, `event_json` (JSON, ver A4), `created_at`, `moves_money` (siempre `false`) |
| `expected_results` | Ground truth | `invoice_id`, `expected_decision`, `case_id` (TC-xxx) |

**Vista `v_metrics`:** une `decisions` y `expected_results` para calcular las métricas de `README (4).md` B6 con una sola consulta.

**Pendiente de decisión:** el acumulado mensual (R6) se calcula sumando `decisions` aprobadas del periodo. BigQuery no es transaccional; ver riesgo R-01.

---

## 6. Google Drive

| Elemento | Decisión |
|---|---|
| Carpeta `blinka-inbox` | Facturas sintéticas (texto y PDF con texto) |
| Carpeta `blinka-processed` | Destino tras evaluar; evita reprocesar |
| Permisos | Cuenta de servicio con acceso **sólo** a esas dos carpetas |
| Alcance | Lectura de `inbox`, mover a `processed`. Sin acceso al resto del Drive |

Drive es sólo canal de entrada. La fuente de verdad de políticas, catálogos y decisiones es BigQuery.

---

## 7. Seguridad, acceso y costos

| Tema | Decisión |
|---|---|
| Identidad del agente | Cuenta de servicio dedicada, mínimo privilegio: lectura de catálogos, **inserción** en `decisions`, sin permiso de escritura sobre `policies` |
| Identidad humana | Quien llama a `PUT /policies` y `POST /decisions/{id}/resolve` se autentica; su identidad queda en el registro |
| Acceso al demo en línea | Autenticación obligatoria (IAP o token de demo). Sin endpoint público anónimo |
| Presupuesto | Alerta de presupuesto en la facturación del proyecto y cuota máxima diaria de llamadas al modelo |
| Datos | Sólo sintéticos (RNF-005). Prohibido cargar facturas reales en Drive |
| Inyección en documentos | El texto de la factura se trata como dato; los prompts de extracción y redacción no tienen herramientas de escritura |

---

## 8. Estructura del repositorio (actualiza `README (2).md` §12)

```text
Reto-30XBlinka/
├── agent/            # ADK 2.0: grafo, nodos, prompts
│   ├── nodes/        # extract, normalize, lookup, policy_engine, router, explain, audit_write
│   └── workflow.py
├── api/              # Cloud Run: endpoints y pantalla simple
├── infra/            # Terraform o scripts: proyecto, BigQuery, Drive, cuentas de servicio
├── data/
│   ├── invoices/     # facturas sintéticas
│   └── fixtures/     # catálogos y expected_results
├── tests/            # reglas, dataset, casos adversariales
├── docs/
└── README*.md
```

---

## 9. Escalabilidad

| Dimensión | Estrategia | Límite conocido |
|---|---|---|
| Cómputo del agente | Agent Runtime gestionado, o Cloud Run con instancias autoescalables | Sin detalles de escalado verificados para Agent Runtime |
| API y UI | Cloud Run, sin estado | — |
| Datos | BigQuery separa almacenamiento y cómputo | No es transaccional |
| Consistencia del presupuesto | Evaluación **en serie** por periodo en el demo | Para producción: Firestore o Spanner para el acumulado, BigQuery para auditoría |
| Reproducibilidad | Mismos datos, política y estado ⇒ mismo resultado de reglas (RNF-004) | El texto de la explicación puede variar; la decisión no |

---

## 10. Riesgos y puntos abiertos

| ID | Riesgo o duda | Mitigación | Estado |
|---|---|---|---|
| R-01 | Condición de carrera en el acumulado mensual (dos facturas ven el mismo saldo) | Procesar en serie; bloqueo por periodo | ABIERTO |
| R-02 | La documentación revisada no detalla endpoints, autenticación ni sesiones de Agent Runtime | Leer esa documentación antes de implementar; plan B: Cloud Run | **POR VERIFICAR** |
| R-03 | Las pausas HITL de 2.0 se mencionan en las notas de migración, sin detalle del mecanismo de reanudación por API | Prototipo mínimo de pausa y reanudación antes de construir el resto | **POR VERIFICAR** |
| R-04 | Gasto no controlado si el demo es accesible | Sección 7: autenticación, alerta y cuota | ABIERTO |
| R-05 | Un `except` amplio tragaría una pausa HITL o un reintento (A3) | Revisión de código y prueba que fuerce una excepción en `policy_engine` | ABIERTO |
| R-06 | Versión exacta de ADK 2.0 a fijar | Fijar versión en `requirements` tras el prototipo | ABIERTO |

---

## 11. Plan de trabajo actualizado

| Fase | Entregable | Estado |
|---|---|---|
| P02 | Este documento: arquitectura, API y datos | DRAFT |
| P03a | Dataset sintético etiquetado + `policies` inicial | PLANNED |
| P03b | `policy_engine` y `router` con pruebas (sin GCP) | PLANNED |
| P03c | Prototipo de pausa/reanudación HITL (cierra R-03) | PLANNED |
| P04a | Proyecto GCP, BigQuery, Drive, cuentas de servicio (cierra R-02, R-04) | PLANNED |
| P04b | Grafo completo + API + pantalla | PLANNED |
| P05 | Métricas, evidencia, guía de demo | PLANNED |

**Orden:** el motor de reglas se construye y se prueba **antes** de tocar GCP, porque es lo que garantiza el criterio eliminatorio de seguridad.

---

**Control documental:** `BLINKA-README-005` · `v0.1.0` · `DRAFT`
**Restricción permanente del MVP:** ninguna transacción real; ninguna aprobación automática fuera de reglas; toda decisión explicable.
