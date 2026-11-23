# Fase 1 · Auditoría de Raíces (17 de noviembre de 2026)

Se compararon tres cosas: el **proyecto original** (zip `traductor-lenguas-indigenas`), el **proyecto actual**
(carpeta `Raices/`, versión entregada el 12-nov) y los requisitos que has dado en los mensajes.

## 1. Cómo estaba el proyecto original

| Pieza | Qué había | Estado |
|---|---|---|
| Rutas Flask (`appy.py`) | `/` y `/login`, `/registro`, `/logout`, `/principal`, `/perfil` (POST), `/palabras/mixteco` (POST), `/recuperar`, `/recuperar/verificar`, `/recuperar/nueva` | Funcionaban |
| Cuentas | Registro (nombre, correo, contraseña con reglas), login con hash, logout, sesión de Flask | Funcionaba |
| Recuperación de contraseña | 3 pasos: correo → **nombre** → nueva contraseña (la plantilla además pedía fecha de nacimiento, que el servidor nunca comprobaba) | Funcionaba, pero **insegura** (basta saber correo y nombre) |
| Perfil | Ventana «Configuración» dentro del panel: nombre (MySQL), pronombre/apodo, biografía, 5 redes (guardados en `perfiles.json`) | Funcionaba |
| Traductor | Español ↔ 4 lenguas con CSV de ~110 palabras y 60 oraciones; sugerencias «¿quisiste decir?», categorías, ejemplos | Funcionaba (solo coincidencia exacta) |
| Aporte de palabras | Botón «Registrar en mixteco»: guarda pares español/mixteco en MySQL, visibles de inmediato | Funcionaba (sin revisión) |
| `perfil.html` | Página «Perfiles de usuario» con tres tarjetas (Administrador, Hablante, Usuario) con botones que no hacían nada | **Sin ruta: nunca se mostraba** |
| Seguridad | Hash de contraseñas, límite de 3 intentos en la recuperación | Sin CSRF, sin límite en login, contraseña de BD y `secret_key` escritas en el código, `debug=True` |
| Sección «Cultura» y «¿Sabías que…?» | Textos generales sobre lenguas y náhuatl | Texto genérico, no ligado a mixteco |
| Audio, variantes, verificación | **No existían** | — |

Plantillas originales: `login`, `registro`, `recuperar`, `dasboard_principal`, `perfil` y parciales `_head`, `_marca`, `_avisos`,
`_iconos`, `_menu_usuario`, `_registro_mixteco`.

## 2. Qué tiene el proyecto actual (antes de esta fase)

| Pieza | Estado |
|---|---|
| Rutas | `/`, `/ejemplos`, `/acerca`, `POST /api/traducir`. **Faltan todas las de cuentas.** |
| Plantillas | `base`, `inicio`, `ejemplos`, `acerca`, `error`. **Faltan registro, login, recuperar, perfil.** |
| Modelos (`models.py`) | Una sesión anterior (interrumpida el 16-nov) ya dejó escritos `Usuario`, `Perfil` y `TokenRecuperacion` además de las tablas lingüísticas. **Ninguna ruta los usa todavía.** |
| `validacion.py`, `texto.py`, `config.py` | Actualizados en esa sesión (reglas de contraseña, perfil, aportes, saltillo, parámetros de login y SMTP). Sin usar aún. |
| Motor | `Traductor` con tres estados y filtro. **`app.py` impide arrancar con cualquier proveedor distinto de `ninguno`; no existe ningún proveedor conectado.** |
| Diccionario | Consulta real a MySQL de traducciones verificadas. No recupera contexto para la IA. |
| Audio | Tabla `audios` lista; **sin ruta, sin reproducción, sin botón.** |
| Interfaz | Contiene lo que pediste quitar: banda «Prototipo académico», tarjetas de demostración con `[texto de demostración]`, aviso repetido en cabecera y pie, `acerca.html` dice que aún se busca al primer hablante. |
| Pruebas | 23 pasan, pero solo cubren rutas públicas, estados y límites. Nada de cuentas. |
| Migraciones | No hay. Solo `flask init-db` con `create_all`. |

## 3. Inventario de pantallas

| Pantalla | Original | Actual | Acción |
|---|---|---|---|
| Inicio / Traductor | Sí (dentro de `/principal`, solo con sesión) | Sí | Rediseñar |
| Ejemplos y vocabulario | No | Sí, con tarjetas de demostración | Rehacer con filtros reales, sin relleno |
| Acerca de Raíces | No | Sí, desactualizada | Actualizar |
| Aviso de privacidad | No | No | **Crear** (es obligatorio por el proveedor de IA) |
| Registro | Sí | **Falta** | Recuperar |
| Inicio de sesión (con «Recordar mi sesión») | Sí | **Falta** | Recuperar |
| Cierre de sesión | Sí | **Falta** | Recuperar |
| Recuperar contraseña | Sí (3 pasos inseguros) | **Falta** | Recuperar con enlace por correo (token de un solo uso) |
| Cuenta / Configuración (nombre, apodo, biografía, redes) | Sí (ventana emergente) | **Falta** | Recuperar como página `/cuenta` |
| Registrar palabra en mixteco | Sí | **Falta** | Recuperar como **aporte pendiente de revisión** (nunca verificado) |
| Perfiles de usuario (Administrador/Hablante/Usuario) | Plantilla sin ruta ni función | No | Ver decisión 2 abajo |
| Errores 400/403/404/405/413/429/500 | No | Sí | Conservar y completar |
| Estados vacíos | No | Parcial | Completar |

## 4. Decisiones que tomé y que puedes revertir

1. **El traductor es público.** En el original solo se veía con sesión, pero nunca se documentó como decisión; tus mensajes lo piden público. Las cuentas dan acceso a Configuración y a «Registrar palabra».
2. **Roles: solo `usuario` y `hablante`.** El «Administrador» del original era texto de una página que nunca funcionó, y pediste no agregar roles administrativos. El rol `hablante` **no se puede elegir al registrarse** (cualquiera podría hacerse pasar por hablante); se asigna con un comando de servidor. En esta versión el rol hablante solo se muestra en la cuenta: la validación se sigue haciendo fuera de la aplicación (ver `proceso_validacion.md`).
3. **Recuperación por correo con token**, no por «nombre completo». Requiere un servidor SMTP; sin él, en desarrollo el enlace se escribe en la consola del servidor y en producción la función queda desactivada con un mensaje claro.
4. **Se retira lo que no aplica al nuevo alcance:** el selector de 4 lenguas, el catálogo de 110 palabras del CSV (sin verificar), la sección de cultura y «¿Sabías que…?».
5. **«Favoritos» e «historial»** aparecían solo como texto en la tarjeta de rol; nunca existieron como función y quedaron fuera del alcance acordado.

## 5. Estado de las funciones solicitadas

| Función | Estado al iniciar esta fase |
|---|---|
| Registro / login / logout / sesión segura | No existe |
| Recuperación de contraseña | No existe |
| Perfil y configuración | No existe |
| Vocabulario desde MySQL con filtros | Parcial (lista simple) |
| Traducción con IA real | **No existe** (bloqueada en `app.py`) |
| Contexto del diccionario para la IA | No existe |
| Avisos de verificación | Parcial |
| Audio (reproducción y botón condicionado) | No existe |
| Privacidad | No existe |
| Migraciones | No existe |
| Publicación en Google Cloud | No existe |

## 6. Problemas encontrados

- `SECRET_KEY` aleatoria en desarrollo invalida las sesiones cada vez que se reinicia (aceptable en local; en producción es obligatoria y ya se exige).
- El límite de solicitudes y el contador diario viven en memoria: con varios procesos o instancias (Cloud Run) cada una cuenta por separado. Es suficiente para el prototipo; el tope real de gasto debe ponerse también en el panel del proveedor de IA.
- Las pruebas del proyecto usan maquetas de SQLAlchemy cuando la librería no está instalada. Eso prueba rutas y lógica, **no** las consultas SQL; ver `tests/test_bd.py`.

---
## Estado al cierre de esta entrega (18-nov-2026)

| Área | Estado | Cómo se comprobó |
|---|---|---|
| Páginas (inicio, ejemplos, acerca, privacidad, errores) | Terminadas y conectadas | pytest + captura en navegador (móvil y escritorio) |
| Registro, login, logout, "recordar sesión", cuenta, cambio y recuperación de contraseña | Terminadas | pytest con repositorio en memoria + flujo real en navegador |
| CSRF (formularios y fetch), origen, bloqueo de login, límites por IP, cabeceras | Terminadas | pytest |
| Aportes de usuario (pendientes) | Terminadas | pytest |
| Traductor: diccionario + contexto + 3 estados + filtro | Terminado | pytest |
| Conectores Anthropic / OpenAI / Gemini | Escritos según la documentación oficial; **sin ninguna llamada real** (no hay claves) | pytest con HTTP simulado |
| Elección del proveedor | **Pendiente**: requiere claves, `scripts/comparar_modelos.py` y la revisión del hablante | — |
| Consultas SQL (`repositorio.py`) y modelos | Escritos; **NO ejecutados** (no se puede instalar SQLAlchemy/MySQL aquí) | `tests/test_bd.py` listo (12 pruebas, omitidas aquí) |
| Migración inicial (Flask-Migrate) | Integrada en `app.py`; **la primera migración debe generarla quien tenga MySQL** | — |
| Audio: ruta, restricciones, botón condicionado | Terminado (sin audios cargados) | pytest |
| Audio real (TTS o grabaciones) | **Pendiente**: autorización y revisión del hablante | `docs/audio.md` |
| Envío de correo | Código listo; **sin SMTP real probado** | pytest (enlace en registro en desarrollo) |
| Google Cloud | Dockerfile y guía; **nada desplegado** | `docs/despliegue_google_cloud.md` |
| Datos lingüísticos | **Ninguno cargado** (a propósito) | — |

El límite por IP y de intentos de login sigue en memoria por instancia; el tope diario de IA ya está en la base de datos.
