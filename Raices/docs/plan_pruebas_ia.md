# Plan de pruebas para comparar modelos de IA

Objetivo: decidir con evidencia qué proveedor y modelo (si alguno) merece conectarse a Raíces para la
variante de Tezoatlán (mxb). El proveedor elegido será **provisional y cambiable**.

No se afirmará que un modelo "soporta" la variante sin los resultados de esta prueba.
Hasta que el hablante apruebe las referencias, no se puede medir calidad lingüística.

## 1. Conjunto de pruebas
El equipo escribe los textos en español; el hablante aporta la traducción de referencia (plantilla:
`plantilla_pruebas_ia.csv`). Tamaño inicial sugerido, ajustable según el tiempo del hablante:

| Tipo | Cantidad | Para medir |
|---|---|---|
| Palabras (varias categorías) | ~40 | vocabulario |
| Frases cortas | ~25 | expresiones |
| Oraciones | ~20 | coherencia y gramática |
| Trampas | ~15 | si el modelo reconoce que no sabe |

Las **trampas** son textos sin equivalente claro, términos modernos, ambiguos (palabras con varios sentidos)
o inventados. La conducta correcta ahí es no proponer traducción, o avisar la duda.
Cuando el hablante dice "no existe equivalente" o da varias opciones, se anota en `notas_hablante` y `alternativas_aceptadas`.

Con ~100 elementos solo se detectan diferencias grandes entre modelos; se debe leer como un indicio, no como una medición fina.

## 2. Condiciones (iguales para todos los modelos)
- **A. Sin contexto:** el modelo recibe solo el texto y las instrucciones.
- **B. Con diccionario:** además recibe entradas verificadas relacionadas (de fuentes autorizadas o aprobadas por el hablante).
  Los textos de prueba **no** pueden aparecer entre esas entradas.

Mismo texto de instrucciones, mismo formato de salida, misma temperatura (0 cuando el modelo la admita),
mismo tope de tokens y **3 ejecuciones** por texto para medir consistencia.
Se registra: modelo exacto, fecha, tokens de entrada y salida, costo y tiempo.

### Instrucción base (se usa idéntica con cada proveedor)
```
Eres un asistente de traducción del español al mixteco de Tezoatlán (código mxb).
Traduce únicamente si tienes información suficiente. No inventes palabras.
No mezcles variantes del mixteco. Si usas entradas del contexto, respétalas tal cual.
Si no puedes traducir con confianza, no propongas una traducción.

Responde SOLO con JSON:
{"traduccion": "<texto o null>",
 "confianza": "alta | media | baja",
 "palabras_sin_respaldo": ["<palabras que no pudiste respaldar>"],
 "motivo": "<por qué no traduces, si traduccion es null>"}

Texto en español: {texto}
Contexto (entradas verificadas, puede estar vacío): {contexto}
```

## 3. Modelos a comparar (uno económico y uno intermedio por proveedor)
Precios oficiales consultados el 12 de noviembre de 2026, en USD por millón de tokens (entrada / salida):

| Proveedor | Económico | Intermedio |
|---|---|---|
| Anthropic | Claude Haiku 5.5: 0.10 / 0.50 | Claude Sonnet 5.5: 2 / 10 |
| OpenAI | GPT-6 Luna: 0.10 / 0.50 | GPT-6.1 Terra: 1 / 5 (o GPT-6.1 Sol: 2 / 10) |
| Google | Gemini 3.5 Flash-Lite: 0.30 / 2.50 | Gemini 3.8 Flash: 0.75 / 3.75 hasta el 31-dic-2026; después 1.50 / 7.50 |

Para Gemini se usa el **nivel de pago**: en el gratuito, Google puede usar el contenido para mejorar sus productos.
Antes de decidir se confirman de nuevo precios, modelos vigentes y condiciones de privacidad.

## 4. Evaluación
**Por el hablante** (por cada propuesta, sin saber qué modelo la generó):
- Fidelidad al significado (0–2)
- Corrección lingüística y de escritura (0–2)
- Uso adecuado del vocabulario (0–2)
- Coherencia (0–2, solo frases y oraciones)
- ¿Sería aceptable mostrarla como "automática sin verificar"? (sí / no)

**Automáticas:**
- chrF contra la referencia (más adecuado que BLEU para lenguas con mucha morfología; depende de acordar la escritura antes).
- Porcentaje de palabras de la propuesta que existen en el vocabulario verificado.
- Consistencia entre las 3 ejecuciones.
- Trampas: cuántas veces el modelo se abstuvo correctamente y cuántas inventó con confianza alta.
- Costo por traducción y tiempo de respuesta.

## 5. Criterio de decisión (propuesta, a acordar con el hablante antes de correr la prueba)
- La calidad en mxb pesa más que el precio o la reputación.
- Si ningún modelo logra propuestas que el hablante considere aceptables en una proporción razonable
  y se abstiene bien en las trampas, **no se activa la IA** y la v1 queda como diccionario verificado
  más la etiqueta "información insuficiente". Eso también es un resultado válido.
- Si algún modelo cumple, se activa con el **filtro de respaldo** (el motor ya lo exige) y se etiqueta siempre
  como "automática sin verificar".

## 6. Privacidad y permisos
- Solo se envían a las APIs textos de prueba en español y entradas de contexto con permiso de uso.
  No se envía contenido de diccionarios de SIL ni de otras fuentes sin su autorización.
- Se usan APIs (no las aplicaciones de chat) y se revisan retención y entrenamiento de cada proveedor.
- Los resultados y las evaluaciones se guardan en un archivo del proyecto, con fecha y versión del modelo.

## 7. Limitaciones que debemos reconocer
- Un solo hablante: sus juicios no representan a toda la comunidad de Tezoatlán.
- La escritura debe acordarse antes; si no, se penaliza o premia por diferencias ortográficas y no por significado.
- Los modelos cambian de versión; los resultados valen para la fecha y versión probadas.
