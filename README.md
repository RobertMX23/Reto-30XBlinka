# Blinka 30X — agente de cuentas por pagar

Blinka recibe facturas, valida sus datos contra proveedores y acuerdos aprobados, registra cada paso y produce una decisión determinista: **PAGAR**, **FRENAR** o **ESCALAR**. El demo no mueve dinero real; muestra el flujo, la trazabilidad ADK y la revisión humana.

## Demo público

- **Interfaz para el comité y el jurado:** https://blinka-30x-2026.web.app
- **API pública:** https://blinka-api-1024016593251.us-central1.run.app
- **ADK Web / trazabilidad:** https://blinka-adk-1024016593251.us-central1.run.app

La URL recomendada para la evaluación es la del frontend. La API y ADK se exponen como superficies técnicas de validación.

## Qué se puede demostrar

1. Enviar una factura como texto estructurado.
2. Clasificar la entrada y extraer campos sin ejecutar instrucciones contenidas en el documento.
3. Validar proveedor, acuerdo, moneda, vencimiento, duplicidad, importe y presupuesto.
4. Obtener una decisión y las reglas que la justifican.
5. Procesar lotes de hasta 100 documentos con concurrencia limitada.
6. Persistir lotes, estados, eventos, decisiones y revisiones en Firestore.
7. Escalar casos ambiguos o fuera del umbral a una revisión humana.
8. Aprobar o rechazar una revisión y conservar quién decidió y cuándo.
9. Observar el flujo y los eventos en ADK Web.

## Alcance del demo

| Incluido | Fuera de alcance del demo |
|---|---|
| Facturas sintéticas y documentos cargados | Movimiento de dinero real |
| Decisiones PAGAR/FRENAR/ESCALAR | Integración bancaria o proveedor de pagos |
| Firestore, Pub/Sub y Cloud Run | Conciliación bancaria productiva |
| Human-in-the-loop por API | Autenticación completa de usuarios |
| Dos tenants de prueba y tres usuarios demo | Auditoría regulatoria completa |
| Frontend Firebase Hosting + ADK Web | OCR avanzado para cualquier PDF escaneado |
| Límite operativo de 10 MB por documento | Operación multiempresa de producción |

## Arquitectura desplegada

```text
Frontend Firebase Hosting
        |
        v
Cloud Run: blinka-api ----> Firestore (lotes, estados, eventos, decisiones, revisiones)
        |
        +----> Pub/Sub: blinka-batch ----> Cloud Run: blinka-worker
        |
        +----> Cloud Run: blinka-adk (ADK Web y trazabilidad)
```

El motor de reglas es determinista. El modelo puede asistir en interpretación o explicación, pero no puede autorizar un pago fuera del contrato. No se almacenan PDF crudos ni instrucciones embebidas como memoria ejecutable.

## Decisiones

| Decisión | Significado |
|---|---|
| `PAGAR` | Todos los controles obligatorios cumplen; se registra una autorización simulada. |
| `FRENAR` | Hay un incumplimiento duro: datos inválidos, proveedor no permitido, duplicado o referencia inexistente. |
| `ESCALAR` | El caso requiere revisión humana: umbral excedido, ambigüedad o excepción de política. |

Los casos escalados se consultan con `GET /reviews` y se resuelven con `POST /reviews/{review_id}/decision` usando `APROBAR` o `RECHAZAR`.

## Evidencia de avance

- Suite local: **114 pruebas pasaron y 1 fue omitida por permisos de symlink** en la última validación registrada.
- Prueba de lote: **30/30 documentos completados**, sin fallos.
- Prueba concurrente: **3 lotes simultáneos completados** sin pérdida de documentos.
- Prueba HITL en Cloud Run: revisión creada para un caso escalado y decisión humana persistida.
- Despliegues activos: API, worker y ADK Web en `us-central1`.
- T12 (auditoría avanzada) queda pendiente para una fase posterior; no bloquea el demo.

## Contratos y documentación

- [Contrato de seguimiento y alcance](docs/contrato-seguimiento-blinka.md)
- [Contratos del workflow](docs/contratos-workflow.md)
- [Arquitectura GCP y ADK](docs/reto-blinka-arquitectura-gcp.md)
- [Especificación del demo](docs/reto-blinka-especificacion-demo.md)
- [Guía local F0/F1/F2](docs/guia-local-f0-f1.md)
- [Registro de madurez y evidencia](docs/registro-madurez.md)

## Desarrollo local

```bash
uv sync
uv run pytest -q
uv run adk web --host 0.0.0.0 --port 8000 --allow_origins="*" agents
```

Para ejecutar el frontend localmente:

```bash
python -m http.server 8080 --directory frontend
```

No se deben guardar claves en Git. En Cloud Run se usan cuentas de servicio y Application Default Credentials; los secretos se administran con Secret Manager.

## Estado del proyecto

El demo end to end está desplegado y listo para evaluación técnica. El siguiente bloque de producto es completar un panel visual de revisiones humanas y después endurecer autenticación, auditoría y OCR para producción.
