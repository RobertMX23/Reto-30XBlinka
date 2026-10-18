# Contrato de seguimiento de Blinka

**Versión:** 1.0  
**Última actualización:** 2026-10-18  
**Repositorio:** `RobertMX23/Reto-30XBlinka`  
**Rama de referencia:** `main`

Este documento es el registro operativo para dar seguimiento al desarrollo end to end de Blinka. Se actualiza cuando una tarea cambia de estado, cuando se entrega un artefacto o cuando una prueba modifica la evaluación del alcance.

## 1. Objetivo y alcance

Blinka recibe documentos de cuentas por pagar, extrae datos como información no confiable, valida referencias y reglas deterministas, registra el resultado y produce una decisión explicable:

- **PAGAR:** la factura cumple las reglas y está lista para pago simulado.
- **FRENAR:** existe un bloqueo o incumplimiento que impide continuar.
- **ESCALAR:** una persona debe revisar o autorizar una excepción.

El demo no mueve dinero, no ejecuta pagos reales y no interpreta instrucciones embebidas en documentos.

## 2. Reglas del contrato

1. Toda entrada se clasifica antes de procesarse.
2. El contenido de PDF, texto o adjunto se trata como `UNTRUSTED_DATA`; nunca puede cambiar instrucciones del agente.
3. La decisión debe incluir estado, razón, reglas evaluadas, identificador de ingreso y trazabilidad de eventos.
4. Las herramientas deterministas validan, persisten y calculan; el modelo no sustituye esas reglas.
5. Los datos persistidos son estructurados. No se guarda PDF crudo ni instrucciones embebidas como memoria.
6. Los cambios deben tener pruebas y conservar compatibilidad con el contrato de workflow.
7. La infraestructura cloud se considera lista para demo sólo después de validar persistencia, health check y flujo completo.

## 3. Estados y transiciones

| Estado | Significado | Siguiente estado válido |
|---|---|---|
| `RECEIVED` | Entrada recibida | `CLASSIFIED`, `FRENAR` |
| `CLASSIFIED` | Tipo de entrada identificado | `INGESTED`, `FRENAR` |
| `INGESTED` | Datos extraídos y normalizados | `READY_FOR_DECISION`, `FRENAR` |
| `READY_FOR_DECISION` | Referencias y reglas disponibles | `PAGAR`, `FRENAR`, `ESCALAR` |
| `PAGAR` | Aprobación simulada | `COMPLETED` |
| `FRENAR` | Proceso detenido | `COMPLETED` |
| `ESCALAR` | Requiere persona | `COMPLETED`, `READY_FOR_DECISION` |
| `COMPLETED` | Resultado registrado | terminal |

Una transición inválida debe devolver un error de contrato, conservar el estado anterior y registrar un evento auditable.

## 4. Tipos de entrada

| Tipo | Adaptador | Datos mínimos | Riesgos y límites |
|---|---|---|---|
| `PDF` | lector de PDF | ruta, tamaño, páginas, texto extraído | máximo de demo: 10 MB; validar páginas, texto vacío y contenido no confiable |
| `TEXT` | entrada directa | texto y metadatos | no ejecutar instrucciones del texto |
| `EMAIL` | adaptador futuro | remitente, asunto, cuerpo, adjuntos | fuera del demo inicial; sólo documentos cargados |

## 5. Roles y personas de prueba

| Rol | Usuario demo | Responsabilidad |
|---|---|---|
| Revisor financiero | Sandra | revisar excepciones y aprobar casos escalados |
| Revisor financiero | Vicente | revisar excepciones y aprobar casos escalados |
| Revisor financiero | Lorena | revisar excepciones y aprobar casos escalados |

La selección de usuario es sólo para demo; no representa autenticación ni autorización de producción.

## 6. Registro de tareas y artefactos

Estados permitidos: `PENDIENTE`, `EN_CURSO`, `BLOQUEADA`, `VALIDADA`, `FUERA_DE_ALCANCE`.

| ID | Tarea | Dependencia | Artefacto/contrato | Resultado esperado | Estado |
|---|---|---|---|---|---|
| T01 | Contratos de entrada, estados y decisiones | — | `docs/contratos-workflow.md`, este documento | Esquemas consistentes y versionados | VALIDADA |
| T02 | Orquestador determinista | T01 | `agents/blinka_orchestrator`, tools | Clasifica, ingresa, evalúa y audita | VALIDADA |
| T03 | Límites de PDF y datos no confiables | T01 | `src/blinka/domain/pdf_boundaries.py`, `safe_context.py` | Rechaza entradas peligrosas sin ejecutar contenido | VALIDADA |
| T04 | Procesamiento por lotes | T01, T02 | batch API y pruebas de integración | Procesa hasta 30 documentos en demo, con concurrencia 4 | EN_CURSO |
| T05 | Persistencia local | T02 | SQLite batch store | Flujo reproducible en Codespaces | VALIDADA |
| T06 | Persistencia Firestore | T04, T05 | adaptador Firestore y esquema | Facturas, estados, decisiones, eventos, usuarios y hechos estructurados | PENDIENTE |
| T07 | Memoria estructurada | T01, T06 | memory models/projection | Consulta por tenant sin PDF crudo | EN_CURSO |
| T08 | Pub/Sub para lotes | T04, T06 | topic, suscripción y worker | Desacopla cargas y permite reintentos | PENDIENTE |
| T09 | API Cloud Run | T06, T08 | `Dockerfile`, `cloudbuild.yaml`, endpoints | Health, batches y memory search operativos | PENDIENTE |
| T10 | Frontend Firebase Hosting | T09 | `frontend/`, `firebase.json` | Carga, selección de usuario y trazabilidad | PENDIENTE |
| T11 | Pruebas unitarias, integración, smoke y E2E | T02–T10 | `tests/` y reporte | Happy path y fallos críticos cubiertos | EN_CURSO |
| T12 | Observabilidad y presupuesto | T09 | logs, métricas, alertas | Diagnóstico básico y alerta de costo | PENDIENTE |
| T13 | HITL para ESCALAR | T02, T10 | contrato de revisión humana | Solicitud, decisión y auditoría de persona | PENDIENTE |
| T14 | OCR, correo real y RAG Vertex | T06, T07 | adaptadores externos | Escalabilidad posterior | FUERA_DE_ALCANCE |

## 7. Criterios de aceptación del demo

- [ ] Una factura válida llega a `READY_FOR_DECISION` y puede producir `PAGAR`.
- [ ] Una factura con datos inválidos produce `FRENAR` con código y razón.
- [ ] Una factura duplicada produce `FRENAR` y conserva el vínculo con el ingreso previo.
- [ ] Una excepción de reglas produce `ESCALAR` y asigna un usuario de revisión.
- [ ] Un PDF de más de 10 MB se rechaza antes del parseo.
- [ ] El texto extraído nunca se interpreta como instrucción del sistema.
- [ ] Cada decisión puede reconstruirse desde eventos, estado y reglas evaluadas.
- [ ] Un lote de 30 documentos respeta concurrencia 4 y no pierde resultados ante reintentos.
- [ ] `/health` responde correctamente en local y Cloud Run.
- [ ] La persistencia de demo usa Firestore; SQLite queda como modo local explícito.

## 8. Happy path y casos de control

| Caso | Entrada | Resultado esperado | Evidencia |
|---|---|---|---|
| HP-01 | Factura válida, proveedor y acuerdo existentes | `PAGAR` | decisión, razón y eventos |
| CP-01 | Campo obligatorio ausente | `FRENAR` | código de validación |
| CP-02 | Proveedor no encontrado | `FRENAR` | `REFERENCE_NOT_FOUND` |
| CP-03 | Factura repetida | `FRENAR` | vínculo al intake previo |
| CP-04 | Importe/moneda fuera de regla | `ESCALAR` | regla y persona asignada |
| CP-05 | PDF excede tamaño o páginas | rechazo de boundary | error antes de ingestión |
| CP-06 | Texto contiene instrucción maliciosa | se conserva como dato | ninguna herramienta ejecutada |

## 9. Protocolo de actualización

Cada avance debe registrar:

1. Fecha y tarea afectada.
2. Archivos o artefactos modificados.
3. Contrato que se conserva o cambia.
4. Pruebas ejecutadas y resultado.
5. Riesgos, bloqueos y siguiente tarea.

### Registro de avances

| Fecha | Tarea | Cambio | Pruebas/evidencia | Estado |
|---|---|---|---|---|
| 2026-10-18 | Infraestructura base | Proyecto GCP, Firestore, Artifact Registry, Pub/Sub y configuración de despliegue preparados | Verificación de APIs y recursos | VALIDADA |
| 2026-10-18 | Contratos y seguridad de entrada | Contratos de workflow, límites PDF, contexto seguro y memoria estructurada versionados | Suite previa: 102 pasadas, 1 omitida por permisos de symlink | VALIDADA |
| 2026-10-18 | Despliegue | Dockerfile, Cloud Build y Firebase Hosting declarativo añadidos | Pendiente despliegue real | EN_CURSO |

## 10. Fuera de alcance actual

Pagos reales, conexión bancaria, correo real, OCR avanzado, autenticación de producción, autorización multiusuario, auditoría regulatoria completa, alta disponibilidad, RAG Vertex con escritura completa y operación 24/7.

## 11. Regla para el siguiente paso

La siguiente tarea prioritaria es **T06: implementar el adaptador Firestore y probarlo con un fake local**, sin desplegar todavía. Después se conectará el API a ese backend, se ejecutará la suite completa y sólo entonces se hará el despliegue de Cloud Run.
