# Registro de madurez de Blinka

Última actualización: 2026-10-17. Las etiquetas M0–M5 son una clasificación del proyecto, no una escala oficial.
Una fase se marca **verificada** solo con evidencia ejecutada y enlazada.

| Fase | Madurez | Estado | Evidencia |
|---|---|---|---|
| F0 | M0 base ejecutable | **Verificada** (Linux y Windows) | [pytest F2 en Windows](../reports/f2-pytest-windows-2026-10-17.txt), [corrida del workflow F1](../reports/f1-adk-workflow-run-2026-10-17.json) |
| F1 | M1 lectura y memoria local | **Verificada** (Linux y Windows) | [pytest F2 en Windows](../reports/f2-pytest-windows-2026-10-17.txt) + [sensibilidad de las pruebas](../reports/f1-sensibilidad-pruebas-2026-10-17.md) |
| F2 | M2 decisión bajo reglas | **Verificada (núcleo)** | [pytest F2 en Windows](../reports/f2-pytest-windows-2026-10-17.txt), [corrida ADK F2](../reports/f2-adk-decision-run-2026-10-17.json) |
| F3 | M3 excepciones controladas | Pendiente | — |
| F4 | M4 lectura asistida por modelo | Pendiente | — |
| F5 | M5 demo en línea | Pendiente | — |

## Qué se comprobó en F0/F1

- `google-adk` **2.11.0** (resuelto en `uv.lock`; el entorno se reconstruyó con `uv sync --frozen`) con `root_agent` como `Workflow` de cinco nodos de función.
- Ejecución real del workflow con `InMemoryRunner`, sin credenciales de Google ni modelo: recorre `read_source → parse_and_validate → load_references → save_intake → recover_receipt` y termina con `decision: null`.
- 79 pruebas pasan en Windows y una de symlink se omite porque el entorno no tiene el privilegio necesario; en Linux la prueba de symlink sí se ejecuta. La suite incluye rutas fuera del directorio, idempotencia, conflicto, reintentos concurrentes (8 hilos), recuperación en procesos separados, texto con instrucción, importe/fecha inválidos y el núcleo de F2.
- F2 compara campos contra política, beneficiario, acuerdo, duplicados y presupuesto; produce PAGAR, FRENAR o ESCALAR, registra una explicación y conserva `moves_money: false`. El workflow ADK F2 usa funciones, no un LLM.
- Las expectativas están en `tests/fixtures/` y una prueba verifica que el código del agente no las referencia.

## Qué NO está demostrado

- **Cobertura completa de decisiones.** Las 22 pruebas T01–T22 de `docs/reto-blinka-especificacion-demo.md` todavía no se ejecutaron como conjunto; F2 cubre ahora los casos base y deja F3 para aprobaciones humanas.
- **SQLite en carpeta sincronizada.** En ese entorno SQLite falló dentro de la carpeta del proyecto (`disk I/O error`); las pruebas y evidencias usaron un disco local. No es un problema del código, pero tampoco se verificó el comportamiento en la carpeta del usuario.
- **Concurrencia entre máquinas, Firestore, API, pantalla, Gemini, PDF/OCR, Drive, BigQuery y GCP:** no existen aún.
- La integración con `adk web` solo se comprobó hasta el descubrimiento del agente (`/list-apps` devolvió `blinka_agent`); no se ejecutó una conversación desde esa interfaz.

## Discrepancias relevantes entre documentos

- Los `README (2)–(5)` son antecedentes. Donde difieren de `docs/`, rige `docs/`: p. ej., beneficiario nuevo = ESCALAR (no BLOCK), máximo absoluto de USD 3,000, y SQLite/Firestore como almacén operativo.
- `README (5).md` afirmaba que BigQuery no es transaccional; es incorrecto (ver `docs/reto-blinka-fases-adk.md` §7). Se añadió una nota de vigencia en ese archivo.
- La política DEMO-v1 se **carga y registra** en F1 (versión y huella), pero no se aplica: no se compara ni se calcula presupuesto.
- `data/reference/` incluye ya a `PROV-N` y acuerdos extra (`AC-A-002`, `AC-B-001`, `AC-N-001`) que F1 solo consulta; F2 los necesitará.
