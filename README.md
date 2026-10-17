# Blinka – agente de pagos de cuentas por pagar (reto 30X)

> Proyecto del reto 30X Blinka. Estado: **en desarrollo** (por ahora este repositorio contiene documentación; el código todavía no existe).

## Tabla de contenidos

- [El problema](#el-problema)
- [Objetivo](#objetivo)
- [Estado actual](#estado-actual)

## El problema

Las empresas reciben constantemente cuentas por pagar (facturas de proveedores, servicios, suscripciones, etc.). Revisarlas una por una para decidir cuáles pagar, cuándo y con qué presupuesto consume tiempo, es propenso a errores (pagos duplicados, montos fuera de lo esperado, proveedores no autorizados) y depende de que alguien recuerde todas las políticas internas.

## Objetivo

Construir un agente que revise las cuentas de una empresa y decida cuáles pagar por ella, dentro de las reglas que la empresa define, y que le pida permiso a una persona cuando algo se sale de esas reglas.

En otras palabras, el agente debe:

1. **Automatizar** los pagos que claramente cumplen las reglas de la empresa.
2. **Escalar** a una persona cualquier caso que se salga de esas reglas o que sea ambiguo.
3. **Dejar registro** de cada decisión y de su motivo.

## Estado actual

- [x] Repositorio creado y flujo de lectura/escritura/PR validado.
- [x] README con la descripción del proyecto.
- [ ] Implementación del agente (ver próximos pasos).
