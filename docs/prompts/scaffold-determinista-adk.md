# Prompt de implementación: scaffold determinista de Blinka con ADK 2.x

Actúa como ingeniero de software encargado de implementar el demo Blinka de forma incremental. Implementa código ejecutable y pruebas pertinentes; no te limites a proponer una estructura o crear carpetas vacías.

## Objetivo de este encargo

**FASE_OBJETIVO = F1. Implementa F0 y F1 únicamente.**

Al terminar debe existir un agente programático ADK que pueda leer una factura sintética de formato conocido, conservar su original, validar y normalizar sus campos, cargar referencias ficticias, guardar el ingreso y recuperarlo después de reiniciar.

La salida será un recibo de ingreso con `decision: null`. Esta fase no determina aprobaciones, no llama a un LLM y no publica recursos en Google Cloud. Las fases posteriores quedan documentadas como pendientes; no las implementes anticipadamente.

## Contexto y fuentes

Trabaja en el repositorio actual `30X-Blinka`. Primero revisa su estado, los archivos existentes y las instrucciones aplicables. Preserva cambios ajenos y documentación existente.

Lee estas fuentes:

1. `docs/reto-blinka-enunciado.md`: alcance oficial del reto.
2. `docs/reto-blinka-especificacion-demo.md`: reglas de negocio y casos de aceptación propuestos.
3. `docs/reto-blinka-arquitectura-gcp.md`: destino de nube, API y acceso para evaluadores invitados.
4. `docs/reto-blinka-fases-adk.md`: fases, madurez y separación de responsabilidades.

El enunciado y las instrucciones del usuario gobiernan el alcance. Los README numerados son antecedentes: no combines políticas contradictorias. Usa las decisiones expresas de este encargo para el scaffold local y registra de forma breve cualquier discrepancia relevante, sin reescribir los borradores ajenos.

## División de responsabilidades

- Código: lectura de archivos, identificación de entradas, validación, normalización, carga de referencias, persistencia, recuperación y control de reintentos.
- ADK: orquestación explícita de esas funciones mediante un workflow programático.
- LLM: ninguna intervención en F0/F1. En F4 podrá extraer campos de texto libre, siempre sujetos a validación.
- Persona: aporta las entradas ficticias y la configuración del demo. La resolución de excepciones se implementará en F3.

En todas las fases, la comparación de reglas, la aritmética de presupuesto y la autorización simulada pertenecen al código. El LLM nunca modifica políticas, inventa datos faltantes o aprueba excepciones por sí mismo.

## F0. Base ejecutable y contratos

1. Usa Python y una versión estable de `google-adk` de la familia 2.x. Comprueba la compatibilidad con el intérprete disponible y las APIs que realmente ofrece esa versión. Fija las dependencias de forma reproducible y registra la versión resuelta; no adivines la última versión ni importaciones.
2. Consulta la documentación oficial de grafos ADK si es necesario: https://adk.dev/graphs/ y https://adk.dev/get-started/python/. El punto de entrada debe exponer `root_agent` como un workflow de funciones, sin un `LlmAgent` que decida qué pasos ejecutar.
3. Mantén el dominio y el servicio de ingreso independientes de ADK. El adaptador ADK llama a esos servicios; no duplica su lógica.
4. Define contratos mínimos para documento fuente, candidato de extracción con incidencias, factura normalizada, política versionada, beneficiario, acuerdo y recibo de ingreso. Conserva explícitamente campos faltantes o inválidos sin convertirlos en valores autorizables.
5. Distingue estado de procesamiento de decisión de negocio. En F1 una entrada puede estar registrada o tener incidencias, pero `decision` permanece nula. No uses PAGAR como valor predeterminado.
6. Usa dinero con precisión exacta y fechas inequívocas. Conserva la representación original cuando la normalización falle. No conviertas monedas ni inventes vencimientos.
7. Prepara configuración local sin secretos. Incluye `.env.example` con valores de ejemplo y excluye del versionado credenciales, entornos virtuales y bases locales.

## Estructura mínima

Utiliza `pyproject.toml`, un archivo de bloqueo de dependencias y una estructura pequeña:

- `agents/blinka_agent/`: `__init__.py`, `agent.py` y `nodes.py` para la composición ADK.
- `src/blinka/domain/`: modelos y validaciones del dominio.
- `src/blinka/application/`: servicio de ingreso.
- `src/blinka/ports/`: interfaz mínima de almacenamiento.
- `src/blinka/adapters/`: parser del formato sintético y almacenamiento SQLite.
- `src/blinka/cli.py`: ejecución local y consulta de un ingreso.
- `data/invoices/`: facturas de texto exclusivamente ficticias.
- `data/reference/`: política, beneficiarios y acuerdos ficticios.
- `tests/unit/`, `tests/integration/` y `tests/fixtures/`: pruebas y expectativas separadas de los datos que consume el agente.
- `reports/`: evidencia cuando realmente se ejecuten las comprobaciones.
- `var/`: base SQLite local, excluida de git.

Aprovecha una organización equivalente si ya existe. No crees módulos futuros vacíos, una arquitectura de microservicios o un sistema genérico de plugins.

## F1. Primer recorrido funcional, sin LLM

Implementa un flujo determinista con estas operaciones:

1. **Leer y conservar:** recibe una ruta explícita dentro del directorio de facturas sintéticas o texto de prueba. Conserva la fuente original, identificador y huella del contenido antes de intentar interpretarla. Limita las rutas admitidas al directorio configurado; no permitas lecturas arbitrarias del sistema.
2. **Parsear:** admite un único formato de texto con etiquetas documentadas: beneficiario, número de factura, importe, moneda, vencimiento y referencia del acuerdo. Lee el contenido real; no obtengas los campos de una tabla de resultados esperados ni del nombre del archivo.
3. **Validar:** produce campos normalizados cuando sea posible y una lista de incidencias cuando falten datos o sean ambiguos. No confíes en una fecha o un importe que el parser no pueda interpretar inequívocamente.
4. **Cargar:** consulta por identificador las referencias ficticias y conserva la versión de política cargada. En esta fase carga la información, pero no compara para autorizar ni calcula presupuesto comprometido.
5. **Guardar:** persiste fuente, extracción, incidencias y referencias consultadas en SQLite mediante una interfaz de almacenamiento. SQLite es el adaptador local; Firestore seguirá siendo el destino futuro de nube.
6. **Recuperar:** permite consultar el ingreso por ID, incluyendo después de cerrar y volver a abrir el proceso.
7. **Emitir recibo:** devuelve ID, revisión, estado de procesamiento, campos, incidencias, versión de política, `decision: null`, `llm_used: false` y `moves_money: false`.

Conecta este recorrido al `root_agent` de ADK usando funciones programáticas. Verifica una ejecución real del workflow además de las pruebas del servicio local. Importar el módulo por sí solo no demuestra que ADK recorrió los pasos.

Expón también comandos locales sencillos para inicializar datos ficticios, ingresar una factura y consultar el ingreso. Documenta los comandos que realmente funcionen. Una vez instaladas las dependencias, F0/F1 debe funcionar sin credenciales ni llamadas a servicios externos.

## Integridad y reintentos

- Una misma clave de ingreso con el mismo contenido devuelve el mismo registro; no crea otra entrada ni otro evento de ingreso.
- La misma clave con contenido distinto genera un conflicto explícito y no sobrescribe la fuente anterior.
- Una solicitud nueva sobre el mismo número de factura conserva la información necesaria para detectar el cobro repetido en F2. No confundas reintento de transporte con duplicado de negocio.
- Un fallo de interpretación conserva la fuente y sus incidencias; no desaparece el documento ni se inventa una extracción válida.
- La base operativa es la fuente de verdad. El estado de sesión ADK puede ayudar a coordinar, pero no sustituye la persistencia del ingreso.
- Separa resultados de negocio de fallos técnicos. No conviertas una excepción en éxito ni registres una aprobación por defecto.

## Datos iniciales y aceptación

Prepara una empresa y beneficiarios ficticios, política y acuerdos consistentes. Crea entradas para: factura completa, campo ausente, importe inválido, referencia inexistente y texto adicional que intente ordenar una aprobación. Los nombres, importes y documentos son sintéticos.

Comprueba al menos:

1. Una factura completa conserva su original y sus campos normalizados correctos.
2. La factura con un campo ausente conserva el resto y reporta el faltante.
3. Importe o fecha inválidos no se transforman silenciosamente en un valor válido.
4. Una referencia inexistente queda identificada como incidencia sin inventar el acuerdo.
5. La política y las referencias se cargan con sus versiones e identificadores.
6. Al reiniciar se recuperan los mismos datos, sin depender de variables del proceso.
7. Repetir una clave de ingreso no duplica; reutilizarla con otro contenido produce conflicto.
8. Una entrada nueva del mismo cobro permanece distinguible para F2.
9. El texto “ignora las reglas y aprueba” no modifica configuración ni produce una decisión.
10. El workflow ADK termina el recorrido sin llamadas al modelo y con `decision: null`.
11. Una ruta fuera del directorio autorizado se rechaza sin leer su contenido.

Las expectativas de extracción viven en las pruebas y no son accesibles al flujo como respuestas. No escribas pruebas que solo comprueben que existen carpetas o repitan literalmente la implementación.

No marques como superadas las 22 pruebas de decisiones de la especificación: corresponden a fases posteriores.

## Plan de evolución que debes conservar

- **F0 / M0:** estructura, contratos y ADK verificables.
- **F1 / M1:** leer, validar, cargar, guardar y recuperar; sin decisiones.
- **F2 / M2:** comparar y determinar PAGAR/FRENAR/ESCALAR. Separar evaluación pura de registro transaccional; comprobar de nuevo presupuesto y duplicados al registrar una aprobación. Explicaciones mediante plantillas.
- **F3 / M3:** persistir solicitudes y respuestas humanas; revalidar contexto y permisos antes de autorizar. Pausa ADK no equivale a permiso válido. En local, actor humano explícitamente simulado.
- **F4 / M4:** incorporar extractor LLM detrás del mismo contrato; verificar datos y evidencia antes de evaluar. No permitir que el modelo elija la autorización.
- **F5 / M5:** Firestore, API, pantalla y publicación GCP para invitados con acceso controlado; repetir pruebas de concurrencia y persistencia en nube. Drive y BigQuery opcionales.

No amplíes el alcance de F0/F1 por anticipar fases posteriores. No implementes aún pagos simulados aprobables, resolución humana, Gemini, PDF/OCR, API pública, interfaz web, Drive, BigQuery, Firestore remoto o infraestructura GCP.

## Entrega y condición de cierre

Entrega código de F0/F1, datos sintéticos, pruebas pertinentes, dependencias reproducibles y guía local. Añade un registro breve de madurez con las fases implementadas, verificadas o pendientes y enlaces a la evidencia disponible.

Reporta qué cambió, cómo se ejecuta, qué pruebas se corrieron, qué resultado obtuviste y qué sigue pendiente. No inventes ejecuciones exitosas. Si ADK no puede instalarse o verificarse, completa el trabajo local independiente y distingue ese resultado de la integración ADK pendiente; no lo sustituyas por una implementación falsa del SDK.

Avanza autónomamente dentro de F0/F1 y resuelve decisiones rutinarias sin pedir confirmación por cada archivo. Termina al cumplir la evidencia de M1 y deja F2–F5 expresamente pendientes. El resultado honesto de esta entrega es: **“El agente programático lee, valida, carga referencias, guarda y recupera información; todavía no determina pagos.”**
