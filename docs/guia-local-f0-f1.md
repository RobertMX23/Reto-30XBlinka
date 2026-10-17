# Blinka F0/F1/F2: guía local

Datos ficticios. Decisiones simuladas. Ninguna operación mueve dinero.

Qué hace hoy el agente: **lee, valida, carga referencias, guarda y recupera información; F2 compara reglas y determina PAGAR, FRENAR o ESCALAR de forma determinista.**

## Requisitos

- Python 3.10 o superior (verificado con 3.10.12) y [uv](https://docs.astral.sh/uv/).
- Sin credenciales, sin Google Cloud y sin llamadas a servicios externos: el workflow ADK de F1 solo usa funciones.

## Instalación reproducible

```bash
uv sync --frozen          # crea .venv con las versiones exactas de uv.lock (google-adk 2.11.0)
```

Sin uv: `python -m venv .venv`, activarlo y `pip install -e . pytest` (versiones sin bloquear).

## Comandos

Desde la raíz del repositorio (con `uv run` no hace falta activar el entorno):

```bash
uv run blinka init                                        # crea la base local y valida las referencias
uv run blinka ingest data/invoices/factura_completa.txt   # ingresa una factura; imprime el recibo
uv run blinka ingest data/invoices/factura_completa.txt --adk   # mismo recorrido, a través del workflow ADK F1
uv run blinka decide INT-XXXXXXXXXXXX                   # aplica las reglas F2 y persiste la decisión
uv run blinka decide INT-XXXXXXXXXXXX --adk              # mismo recorrido, a través del workflow ADK F2
uv run blinka show INT-XXXXXXXXXXXX --source              # recupera un ingreso (también tras reiniciar)
uv run pytest                                             # pruebas
```

`ingest --text "Beneficiario: PROV-A ..."` acepta texto de prueba. `--key` fija la clave de ingreso (idempotencia).
Códigos de salida: `0` correcto, `1` fallo técnico, `2` entrada rechazada, `3` conflicto de clave.

## Qué decide F2

La evaluación determinista compara moneda, beneficiario permitido, acuerdo, duplicidad, máximo por factura, presupuesto y umbral automático. Devuelve:

- `PAGAR` con autorización `AUTOMATICA` cuando todo cumple y compromete el presupuesto una sola vez.
- `FRENAR` ante un impedimento duro, como duplicado, discrepancia de acuerdo, importe inválido, máximo o presupuesto excedido.
- `ESCALAR` cuando falta información, no hay política para la moneda, el beneficiario requiere permiso o el importe supera el umbral automático.

La decisión se guarda dentro del recibo con reglas, evidencia, razones, versión de política y presupuesto. El workflow F2 sigue compuesto solo por funciones ADK; F4 será la fase que podrá usar un LLM para extracción asistida.

Para probar el agente con la interfaz de desarrollo de ADK (opcional): `uv run adk web agents`.

## Orquestador multiagente determinista

El agente `blinka_orchestrator` coordina la entrada y, opcionalmente, la decisión F2. En esta primera etapa admite `TEXT` y `TXT_FILE`; `PDF_TEXT`, `PDF_SCAN`, `IMAGE`, `EMAIL` y `EMAIL_ATTACHMENT` se rechazan de forma explícita hasta que se incorporen sus adaptadores.

El orquestador conserva las invariantes del servicio existente: idempotencia, recibo recuperable, decisiones explicables y `moves_money: false`. Sus tools de clasificación y conservación están en `src/blinka/tools/` y sus contratos de tipos y estados en `src/blinka/domain/input_models.py`.

## Configuración

Variables en `.env` (copiar `.env.example`; no contiene secretos): `BLINKA_INVOICES_DIR`, `BLINKA_REFERENCE_DIR`, `BLINKA_DB_PATH`.
La base es `var/blinka.db` (SQLite, fuera de git).

> **Nota de entorno:** en el sandbox donde se verificó F1, SQLite no podía crear su archivo de journal dentro de la carpeta
> sincronizada del proyecto (`disk I/O error`). Allí se usó `BLINKA_DB_PATH` apuntando a un disco local. En Windows se
> verificó la suite y el CLI usando `var/f1-check.db`; la única prueba omitida requiere privilegios para crear symlinks.

## Formato de factura admitido

Texto UTF-8 con una etiqueta por línea (mayúsculas y acentos no importan):

| Etiqueta | Campo | Regla |
|---|---|---|
| `Beneficiario:` | identificador del beneficiario | letras, números, `.`, `_`, `-` |
| `Número de factura:` | número | letras, números, `.`, `_`, `/`, `-` |
| `Importe:` | importe | `1234.56` o `1,234.56`; hasta 2 decimales; `1.500,00` es **inválido** (ambiguo) |
| `Moneda:` | código de 3 letras | no se convierte |
| `Vencimiento:` | fecha | solo `AAAA-MM-DD` existente |
| `Acuerdo:` | referencia del acuerdo | debe existir en `data/reference/agreements.json` |
| `Notas:` | texto libre | se conserva en la fuente; nunca se interpreta |

Un campo ausente, vacío, con valores contradictorios o inválido se registra como **incidencia**; el resto se conserva.

## Contratos clave

- **Recibo de ingreso:** `intake_id`, `revision`, `processing_status` (`REGISTRADA` / `REGISTRADA_CON_INCIDENCIAS`), campos, incidencias,
  referencias consultadas, `policy_version`, `decision: null`, `llm_used: false`, `moves_money: false`.
- **Idempotencia:** misma clave + mismo contenido → mismo registro (`REPLAYED`). Misma clave + otro contenido → error `INGEST_CONFLICT`, sin sobrescribir.
- **Mismo cobro, entrada nueva:** otra clave con mismo beneficiario + número de factura crea otro ingreso con el mismo `business_key`
  y lista los anteriores en `earlier_intake_ids`. F1 **no** lo frena; eso corresponde a F2.
- **Rutas:** solo `.txt` dentro de `data/invoices/`; cualquier otra se rechaza **antes** de leerla.

## Estructura

```
agents/blinka_agent/   root_agent (Workflow de funciones) y nodos finos
src/blinka/            domain/ application/ ports/ adapters/ cli.py (independiente de ADK)
data/invoices/         facturas ficticias      data/reference/   política DEMO-v1, beneficiarios, acuerdos
tests/                 unit/ integration/ fixtures/ (expectativas; el agente nunca las lee)
reports/               evidencia de ejecución  var/             base local (ignorada por git)
```
