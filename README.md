# Raíces · traductor español → mixteco

Aplicación web en Flask, SQLAlchemy y MySQL. Variante inicial (candidata): Mixteco de Tezoatlán (`mxb`),
pendiente de confirmar con la persona hablante. Cada traducción lleva una de tres etiquetas:
**verificada**, **automática sin verificar** o **información insuficiente**.

## Qué incluye
- **Traductor público** (sin cuenta): diccionario verificado + IA con el diccionario como contexto.
- **Ejemplos y vocabulario**: lee MySQL (filtros, paginación, procedencia). Estado vacío si no hay contenido.
- **Cuentas**: registro, inicio/cierre de sesión, "recordar sesión", perfil, cambio y recuperación de contraseña por correo.
- **Aportes**: un usuario puede proponer una palabra; queda *pendiente* y nunca se muestra como verificada.
- **Roles**: solo `usuario` y `hablante` (el de hablante lo asigna quien administra el servidor).
- **Audio**: solo se ofrece si hay una grabación aprobada y autorizada (`/audio/<id>`). Ver `docs/audio.md`.
- **Aviso de privacidad** y límites de uso (texto, solicitudes por IP, intentos de login, tope diario de IA).

## Estructura
```
Raices/
├── SRC/
│   ├── app.py            Crea la app, CSRF global, errores, comandos (init-db, asignar-rol)
│   ├── config.py         Configuración (lee .env)
│   ├── models.py         Tablas (usuarios, variantes, traducciones, fuentes, validaciones, audios…)
│   ├── rutas.py          Páginas públicas, /api/traducir y /audio/<id>
│   ├── cuentas.py        Registro, login, cuenta, aportes, recuperación
│   ├── seguridad.py      Límites, CSRF y cabeceras
│   ├── servicios/        repositorio.py (TODO el SQL) · traductor.py · ia.py · filtro.py
│   │                     validacion.py · texto.py · correo.py · tipos.py
│   ├── templates/ · static/
├── tests/                pytest (con repositorio en memoria + test_bd.py con SQLAlchemy real)
├── scripts/comparar_modelos.py   Compara proveedores de IA con los mismos textos
├── docs/                 auditoria · despliegue_google_cloud · audio · plan_pruebas_ia · proceso_validacion
├── Dockerfile · requirements.txt · .env.example
```

## Guía rápida para Windows + Visual Studio Code
Los pasos 1–5 y 8 son los habituales; el flujo de traducción con Gemini **no se ha probado con una llamada real** hasta que tú
lo hagas en el paso 6 (el autor del código no tiene tu clave).

1. **Abrir el proyecto.** Extrae el ZIP. En VS Code: *Archivo → Abrir carpeta* y elige la carpeta `Raices` (la que contiene `SRC`, `tests`, `README.md`).
2. **Entorno virtual** (terminal de VS Code, *Terminal → Nueva terminal*):
   ```
   python -m venv .venv
   .venv\Scripts\activate
   ```
   Si PowerShell bloquea el script: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y repite.
3. **Dependencias:** `pip install -r requirements.txt`
4. **Archivo `.env`:** ya viene creado en la carpeta `Raices` (si no existe, cópialo: `copy .env.example .env`).
5. **Clave de Gemini:** abre `.env` y escribe tu clave después de `GEMINI_API_KEY=` (sin comillas ni espacios). Guarda. **No subas `.env` a GitHub ni lo compartas.**
6. **Prueba de la clave (1 sola llamada real a Gemini):**
   ```
   python scripts/probar_gemini.py "hola"
   ```
7. **Base de datos:** con el SQLite de desarrollo (no necesitas MySQL) las tablas se crean solas al arrancar. Si prefieres hacerlo a mano:
   ```
   cd SRC
   flask --app app init-db
   ```
8. **Ejecutar** (desde la carpeta `SRC`):
   ```
   cd SRC
   python app.py
   ```
   Abre **http://127.0.0.1:5000** en el navegador. El traductor es público (no pide cuenta).
9. **Probar una traducción:** escribe una palabra o frase en español y pulsa *Traducir*. Verás "Automática sin verificar" con el aviso obligatorio, porque todavía no hay vocabulario verificado. Cada traducción de este tipo hace **una llamada** a Gemini (límite diario configurable: `LIMITE_DIARIO_IA`).

### Errores comunes
| Mensaje | Causa y solución |
|---|---|
| `Could not import 'app'` | Estás en la carpeta equivocada: ejecuta `flask`/`python app.py` desde `SRC`. |
| La página dice "la traducción automática no está activada" | Falta `GEMINI_API_KEY` en `.env` (o `PROVEEDOR_IA=ninguno`). Reinicia la app tras editar `.env`. |
| "El servicio de traducción automática no respondió" | Mira la consola: `código 400/403` = clave inválida o sin permiso, `404` = modelo no disponible (revisa `MODELO_GEMINI`), `429` = límite de uso de Google, "sin conexión" = internet o proxy. |
| "El servicio no está disponible por el momento" | Error de base de datos: revisa la consola (`OperationalError` = conexión; `ProgrammingError` = faltan tablas → `flask --app app init-db`). |
| `ModuleNotFoundError` | Falta activar el entorno virtual o instalar dependencias (pasos 2 y 3). |
| Cambié `.env` y nada cambia | Detén la app (Ctrl+C) y vuelve a iniciarla. |

### Error `1054 Unknown column …` o 503 al usar MySQL
Ocurre cuando la base MySQL se creó con una versión anterior del proyecto: `init-db` crea tablas que faltan, pero **no agrega columnas** a las que ya existen.
1. Comprueba: `flask --app app revisar-bd` (lista tablas y columnas que faltan; también avisa al arrancar la app).
2. **Si la base no tiene datos que conservar** (lo normal ahora): bórrala y recréala limpia.
   ```
   DROP DATABASE raices;
   CREATE DATABASE raices CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
   y luego `flask --app app init-db` (o `SOURCE docs/mysql/schema_completo.sql;` dentro de `USE raices;`).
3. **Si hay datos que conservar:** haz copia (`mysqldump -u USUARIO -p raices > respaldo.sql`), ejecuta `flask --app app init-db` y después
   `mysql -u USUARIO -p raices < docs/mysql/migracion_desde_v1.sql` (repetible, no borra nada).
4. Verifica: `flask --app app revisar-bd` debe decir que coincide.

### MySQL (opcional)
Rellena `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME` en `.env` (MySQL 8.0.16+ y la base creada con `CREATE DATABASE raices CHARACTER SET utf8mb4;`) y ejecuta `flask --app app init-db`.
Para producción usa migraciones (`flask --app app db init / migrate / upgrade`); no se pudieron generar aquí.

### Pruebas automáticas
`pytest` (desde la carpeta `Raices`). No consumen la API de Gemini: usan respuestas simuladas.

## Traducción automática (IA)
Por defecto `PROVEEDOR_IA=ninguno`: solo se muestran traducciones verificadas, y la app lo dice abiertamente.
Para activarla: pon `GEMINI_API_KEY` en `.env` (Gemini es el predeterminado; también hay `anthropic` y `openai`). Si falta la clave,
la app arranca con la IA desactivada y lo avisa. El proveedor se cambia solo con esa variable. La elección del proveedor **no está hecha**:
requiere `scripts/comparar_modelos.py` y la revisión de la persona hablante (ver `docs/plan_pruebas_ia.md`).

## Pruebas
```
pytest
```
Las pruebas de rutas, cuentas, motor y proveedores no necesitan base de datos ni claves (usan un repositorio en
memoria y una capa HTTP simulada: no son llamadas reales). `tests/test_bd.py` prueba las consultas reales con
SQLAlchemy y se omite si no está instalado.

## Qué falta (depende de personas, claves o permisos; nada se finge)
- Datos lingüísticos: la base empieza **vacía** a propósito. Los carga/valida la persona hablante (`docs/proceso_validacion.md`).
- Confirmar con la persona hablante su variedad y el código ISO; criterios de escritura (tonos, saltillo).
- Claves de API y la comparación de modelos con el hablante → elegir proveedor.
- Servidor de correo (SMTP) para la recuperación de contraseña en producción.
- Audio: grabaciones con autorización (o evaluar TTS con el hablante). Ver `docs/audio.md`.
- Permisos de las fuentes publicadas (hasta tenerlos, no se publica su contenido).
- Publicación en Google Cloud: preparada y documentada, **no ejecutada** (`docs/despliegue_google_cloud.md`).
