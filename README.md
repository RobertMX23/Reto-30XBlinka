# Blinka – agente de pagos de cuentas por pagar (reto 30X)

> Proyecto del reto 30X Blinka. Estado: **en desarrollo** (por ahora este repositorio contiene documentación; el código todavía no existe).

## Tabla de contenidos

- [El problema](#el-problema)
- [Objetivo](#objetivo)
- [Cómo funciona el agente](#cómo-funciona-el-agente)
- [Diagrama de flujo](#diagrama-de-flujo)
- [Reglas de ejemplo](#reglas-de-ejemplo)
- [Estado actual](#estado-actual)

## El problema

Las empresas reciben constantemente cuentas por pagar (facturas de proveedores, servicios, suscripciones, etc.). Revisarlas una por una para decidir cuáles pagar, cuándo y con qué presupuesto consume tiempo, es propenso a errores (pagos duplicados, montos fuera de lo esperado, proveedores no autorizados) y depende de que alguien recuerde todas las políticas internas.

## Objetivo

Construir un agente que revise las cuentas de una empresa y decida cuáles pagar por ella, dentro de las reglas que la empresa define, y que le pida permiso a una persona cuando algo se sale de esas reglas.

En otras palabras, el agente debe:

1. **Automatizar** los pagos que claramente cumplen las reglas de la empresa.
2. **Escalar** a una persona cualquier caso que se salga de esas reglas o que sea ambiguo.
3. **Dejar registro** de cada decisión y de su motivo.

## Cómo funciona el agente

El flujo previsto tiene cinco etapas:

1. **Ingesta de cuentas.** El agente recibe las cuentas por pagar (por ejemplo, facturas en PDF/XML, un CSV o una API) y extrae los datos clave: proveedor, monto, moneda, fecha de emisión, fecha de vencimiento, categoría y número de factura.
2. **Evaluación contra las reglas de la empresa.** Cada cuenta se compara con las reglas que define la empresa, por ejemplo:
   - **Monto máximo** que se puede pagar sin aprobación humana.
   - **Proveedores aprobados** (lista blanca) y proveedores bloqueados.
   - **Fecha de vencimiento**: priorizar lo que vence pronto y no pagar antes de cierta ventana.
   - **Presupuesto por categoría**: no exceder lo asignado a cada categoría en el periodo.
   - **Duplicados**: detectar la misma factura (mismo proveedor + número o mismo monto y fecha) para no pagarla dos veces.
3. **Decisión.** Para cada cuenta el agente decide una de tres acciones:
   - ✅ **Pagar**: cumple todas las reglas.
   - 🙋 **Escalar a una persona**: se sale de alguna regla “suave” (por ejemplo, supera el monto máximo o el presupuesto) o hay información ambigua.
   - ⛔ **Rechazar**: incumple una regla “dura” (por ejemplo, duplicado confirmado o proveedor bloqueado).
4. **Aprobación humana (human-in-the-loop).** Las cuentas escaladas se envían a la persona responsable con un resumen y el motivo. Esa persona aprueba, rechaza o pide más información; el agente no paga nada escalado sin esa respuesta.
5. **Registro de auditoría.** Cada decisión queda registrada: qué cuenta, qué reglas se evaluaron, qué resultado dio cada una, qué decidió el agente (o la persona) y cuándo.

## Diagrama de flujo

```mermaid
flowchart TD
    A[Cuenta por pagar recibida] --> B[Extraer datos: proveedor, monto, fechas, categoría]
    B --> C{Evaluar reglas de la empresa}
    C -->|Incumple regla dura: duplicado, proveedor bloqueado| R[Rechazar]
    C -->|Se sale de una regla: monto, presupuesto, datos ambiguos| H[Escalar a una persona]
    C -->|Cumple todas las reglas| P[Programar / ejecutar pago]
    H --> D{Decisión humana}
    D -->|Aprueba| P
    D -->|Rechaza| R
    P --> L[(Registro de auditoría)]
    R --> L
    D -.->|Pide más información| B
```

## Reglas de ejemplo

> **Ejemplo ilustrativo.** El formato y los valores son una propuesta; cada empresa definiría los suyos.

```yaml
# reglas.yaml (ejemplo)
moneda_base: MXN

limites:
  monto_maximo_sin_aprobacion: 20000      # arriba de esto, escalar
  monto_maximo_absoluto: 250000           # arriba de esto, rechazar

proveedores:
  aprobados:
    - "Proveedor Ejemplo SA de CV"
    - "Servicios Demo SC"
  bloqueados:
    - "Proveedor Bloqueado SA"
  desconocido: escalar                    # proveedor fuera de las listas

vencimiento:
  pagar_dias_antes_de_vencer: 3           # no pagar antes de esta ventana
  vencida: escalar                        # cuentas ya vencidas

presupuesto_mensual_por_categoria:
  software: 50000
  servicios_profesionales: 80000
  oficina: 15000
  al_exceder: escalar

duplicados:
  criterio: [proveedor, numero_factura]
  al_detectar: rechazar

aprobadores:
  - nombre: "Responsable de finanzas"
    canal: email
```

## Estado actual

- [x] Repositorio creado y flujo de lectura/escritura/PR validado.
- [x] README con la descripción del proyecto.
- [ ] Implementación del agente (ver próximos pasos).
