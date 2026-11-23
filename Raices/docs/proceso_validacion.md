# Proceso de validación lingüística

Objetivo: que una persona hablante de la variante revise contenido **sin usar la aplicación**, y que
cada revisión quede registrada. Nada se marca como "verificada" sin una revisión real.

## Principios
1. Se valida el **texto exacto** que se mostrará. Una oración no queda verificada porque sus palabras lo estén.
2. Cada revisión registra: qué contenido, quién lo revisó, cuándo, para qué variante y el resultado
   (tabla `validaciones`).
3. La participación es voluntaria y con consentimiento expreso (ver más abajo).
4. Una propuesta de IA nunca se considera verificada hasta que el hablante la apruebe o la corrija.

## Material para el hablante
Un archivo sencillo (Excel, Google Sheets o CSV) con la plantilla `plantilla_validacion.csv`.
El hablante solo llena tres columnas: **resultado**, **texto_mixteco_corregido** y **comentario**.

| Columna | Quién la llena | Contenido |
|---|---|---|
| lote, id_interno, tipo, texto_es | Equipo | Texto en español y tipo (palabra, frase, oración) |
| texto_mixteco_propuesto | Equipo | Propuesta a revisar (puede venir de una fuente, de IA o estar vacía) |
| origen_propuesta | Equipo | `fuente_publicada`, `hablante` o `ia` |
| resultado | Hablante | `aprobada`, `corregida` o `rechazada` |
| texto_mixteco_corregido | Hablante | Solo si el resultado es `corregida` (o si no había propuesta) |
| comentario | Hablante | Uso, contexto, observaciones, "no existe equivalente", etc. |
| revisor, fecha_revision | Hablante o equipo | Nombre público acordado y fecha |

## Ronda de validación (paso a paso)
1. **Preparar el lote.** El equipo genera un archivo con pocos elementos (se sugiere empezar con unos 30–40,
   para que la sesión sea corta; se ajusta con el hablante).
2. **Enviar.** Por el medio que prefiera el hablante (correo, mensajería, reunión). No requiere cuenta ni la web.
3. **Revisar.** El hablante marca cada fila. Si prefiere, puede dictar por voz y el equipo transcribe, pero
   la escritura final siempre se confirma con él.
4. **Recibir y revisar el archivo.** El equipo comprueba que no haya filas vacías ni caracteres extraños.
5. **Importar.** Se cargan las filas a MySQL (script de importación, pendiente de construir):
   - `aprobada` → `estado = verificada`, `verificada_por_id` y `verificada_en` con los datos del revisor.
   - `corregida` → se guarda el texto corregido y queda verificada con ese texto.
   - `rechazada` → `estado = rechazada` (no se muestra).
   - En todos los casos se agrega una fila a `validaciones`.
6. **Registrar el lote** (fecha, cantidad, quién importó) en un cuaderno o bitácora del proyecto.

## Consentimiento (mínimo por escrito, puede ser un mensaje confirmado)
- Que su trabajo se use en Raíces y, si se decide, en versiones posteriores.
- Cómo quiere aparecer en los créditos (nombre, seudónimo o ninguno).
- Bajo qué licencia comparte sus traducciones (por decidir con él; el equipo propondrá opciones).
- **Audio aparte:** autorización expresa para grabar y para publicar cada grabación.
- Que puede pedir retirar su contenido.
- Si habrá alguna compensación o reconocimiento, acordarlo desde el inicio.

## Primera sesión: criterios de escritura (antes de cargar nada)
Decisiones que se toman con el hablante y se documentan:
1. Alfabeto o convención de escritura que seguirá Raíces para Tezoatlán.
2. Cómo se escriben los **tonos** (acentos, números u otra marca).
3. Qué carácter se usa para el **saltillo** (por ejemplo `'` o `ꞌ`). Debe ser uno solo en toda la base.
4. Vocales nasalizadas y alargadas: cómo se marcan.
5. Si hay variación entre comunidades de Tezoatlán que conviene registrar.

Todo el texto en mixteco se guarda en Unicode normalizado (NFC) y con esas reglas.

## Audio (segunda etapa)
- Solo se graban elementos ya validados y con autorización expresa por cada uno.
- Una grabación por palabra, frase u oración completa; **no** se unen audios de palabras para formar oraciones.
- Se registra quién grabó, cuándo y la autorización (tabla `audios`).
- Un modelo de voz sintética solo se usaría si su calidad en la variante queda demostrada por el hablante.
