# Audio y pronunciación — estado y decisiones

**Estado: la función está implementada y conectada, pero NO hay ningún audio cargado.** Sin audios, ningún botón aparece.

## Qué ya funciona (probado)
- Tabla `audios` con traducción, variante (a través de la traducción), tipo de origen (`grabacion` | `tts`), hablante, autorización y estado.
  Una grabación exige hablante y `autorizado = 1` (restricción de la base de datos).
- `/audio/<id>` solo entrega el archivo si el audio está **aprobado**, **autorizado** y su traducción es **visible**
  (verificada, variante activa, fuente con permiso). Rechaza rutas fuera de la carpeta de audios (`AUDIO_DIR`).
- El botón «▶ Escuchar» solo se dibuja cuando el servidor devuelve `audio_url`; no hay botones decorativos ni audios de muestra.

## Alternativa A — voz sintética (TTS)
- Existe en Hugging Face un modelo de Meta MMS para el código `mxb` (`facebook/mms-tts-mxb`), de unos 145 MB, con licencia **CC-BY-NC-4.0**
  (no comercial). No pude leer su ficha desde este entorno (el sitio no es accesible), así que **no está confirmado** qué variedad
  documenta, ni su calidad.
- Que el código coincida no prueba que suene bien ni que sea la variedad de la persona hablante. **No se usa** hasta que ella revise una muestra.
- Si se aprueba: generar los archivos fuera de la app, registrarlos con `origen='tts'`, `estado='aprobado'`, y decidir si la licencia no comercial es compatible con el uso del proyecto.

## Alternativa B — grabaciones con la persona hablante (preferida)
1. Obtener por escrito su autorización para **grabar, almacenar y reproducir** (modelo en `docs/proceso_validacion.md`), y si desea créditos (`consentimiento_creditos`).
2. Grabar palabras/frases ya verificadas; guardar los archivos en `AUDIO_DIR` (mp3 o wav).
3. Registrar cada archivo en `audios` con `origen='grabacion'`, `hablante_id`, `autorizado=1`, `estado='aprobado'` tras su revisión.
   Aún no existe una pantalla para esto (se decidió no crear paneles de administración): se hace con SQL o con un script cuando haya audios reales.

## En la nube
Los archivos no deben ir en el contenedor. Opción: Cloud Storage montado como volumen en Cloud Run (`AUDIO_DIR=/audios`). Ver `docs/despliegue_google_cloud.md`.
