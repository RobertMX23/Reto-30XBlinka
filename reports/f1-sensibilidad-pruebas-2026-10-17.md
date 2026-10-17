# F1: ¿las pruebas detectan defectos reales?

Se introdujo un defecto a la vez en el código (restaurado después; diff idéntico a la copia original) y se corrió la suite.
Resultado observado el 2026-10-17:

| Defecto introducido | Archivo | Resultado |
|---|---|---|
| Desactivar la comprobación de que la ruta esté dentro del directorio autorizado | `adapters/fixture_reader.py` | **Falla** `test_path_outside_directory_is_rejected_without_reading_it` |
| Tratar un conflicto de clave como repetición | `adapters/sqlite_store.py` | **Falla** `test_workflow_replay_and_conflict` |
| Aceptar cualquier fecha inválida como válida | `domain/validation.py` | **Falla** `test_every_synthetic_invoice_matches_its_expectation[factura_fecha_invalida.txt]` |
| Resolver un campo contradictorio eligiendo uno | `domain/validation.py` | **Falla** `test_conflicting_override_attempt_in_notes_is_ambiguous_not_obeyed` |
| Sin defecto (control) | — | 71 pruebas pasan |

Cada ejecución usó `-x` (se detiene en el primer fallo), así que no mide cuántas otras pruebas también lo detectarían.
