# Publicación en Google Cloud (preparada, NO ejecutada)

> No se creó ningún recurso ni se desplegó nada. Este documento y el `Dockerfile` dejan todo listo; los comandos
> de abajo los ejecutas tú cuando lo decidas, porque **generan costos en tu cuenta**.
> Precios consultados en la documentación oficial de Google Cloud el 17-nov-2026 (en dólares; pueden cambiar).

## Arquitectura propuesta (sin sobreingeniería)
| Pieza | Servicio | Por qué |
|---|---|---|
| App Flask | **Cloud Run** (contenedor con gunicorn) | Ya termina HTTPS y balancea: **no hace falta Nginx**. Escala a cero. |
| MySQL | **Cloud SQL for MySQL** (8.0+) | Es lo que usa el proyecto (utf8mb4, restricciones CHECK). |
| Claves | **Secret Manager** | `SECRET_KEY`, contraseña de la BD, claves de IA, SMTP. Nada en el repositorio ni en el contenedor. |
| Audios | **Cloud Storage** (solo cuando existan audios) | Montado como volumen en Cloud Run → `AUDIO_DIR`. |
| Copias | Copias automáticas de Cloud SQL | Ver costos. |

## Costos verificados (región us-central1)
- **Cloud Run** (facturación por solicitud): gratis cada mes 2 millones de solicitudes, 180 000 vCPU-s y 360 000 GiB-s; después, USD 0.40 por millón de solicitudes más CPU/memoria.
- **Cloud SQL MySQL, instancia compartida `db-f1-micro`** (0.6 GiB): **USD 0.0105/hora ≈ USD 7.7/mes**, sin alta disponibilidad; `db-g1-small`: USD 0.035/hora ≈ 25.5/mes. Las instancias compartidas **no están cubiertas por el SLA**.
  Almacenamiento SSD ≈ USD 0.17/GiB-mes (mínimo habitual 10 GiB ≈ 1.7); copias ≈ USD 0.08/GiB-mes usado. Nuevos clientes: USD 300 de crédito por 90 días. Cloud SQL no está en el nivel siempre gratuito.
- **Secret Manager**: 6 versiones activas y 10 000 accesos al mes gratis; luego ≈ USD 0.06 por versión-mes y USD 0.03 por 10 000 accesos.
- **Cloud Storage**: 5 GB-mes gratis solo en us-west1, us-central1 y us-east1; después ≈ USD 0.02/GiB-mes. México (northamerica-south1) no entra en el nivel gratuito.
- **Cloud Logging**: 50 GiB/mes gratis. **Cloud Build**: 2 500 min/mes gratis. **Artifact Registry**: 0.5 GB gratis.
- **IA**: *no verificado todavía* (depende del proveedor y modelo elegidos). El tope `LIMITE_DIARIO_IA` y los límites por IP acotan el gasto: gasto máximo diario = límite × costo por llamada. Pon también un tope de gasto en el panel del proveedor.

## ¿Cabe en ~150 MXN al mes?
Probablemente **no con Cloud SQL**: solo `db-f1-micro` + 10 GiB ya suma ≈ USD 9.4/mes, y 150 MXN equivalen a unos 7–9 USD según el tipo de cambio del día (compruébalo), antes de contar la IA. Opciones, de menor a mayor esfuerzo:
1. **Cloud Run + Cloud SQL `db-f1-micro`** (≈ USD 9–10/mes + IA): lo más simple y gestionado; excede el presupuesto objetivo por poco.
2. **Cloud Run + MySQL gestionado de otro proveedor con plan gratuito/barato**: baja el costo, pero no se evaluó aquí y agrega latencia entre nubes.
3. **Una sola VM `e2-micro` con MySQL y la app** dentro del nivel gratuito de Compute Engine (1 VM en us-west1/us-central1/us-east1, 30 GB de disco estándar, 1 GB de salida/mes): casi gratis, pero tú administras el servidor (parches, copias, HTTPS) y 1 GB de salida es poco. Aquí sí harían falta Nginx/Caddy y certificados.
Recomendación provisional: empezar con la opción 1 aprovechando el crédito de 300 USD, medir el consumo real y decidir después.

## Pasos (cuando decidas publicar)
Sustituye `PROYECTO` y `REGION` (p. ej. `us-central1`). Todos estos comandos cuestan o crean recursos.
```bash
gcloud config set project PROYECTO
gcloud services enable run.googleapis.com sqladmin.googleapis.com secretmanager.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com

# 1. Base de datos
gcloud sql instances create raices-mysql --database-version=MYSQL_8_0 --tier=db-f1-micro --region=REGION \
       --storage-size=10 --backup-start-time=04:00
gcloud sql databases create raices --instance=raices-mysql
gcloud sql users create raices_app --instance=raices-mysql --password='<contraseña larga>'

# 2. Secretos (uno por valor)
printf '%s' "$(python -c 'import secrets;print(secrets.token_hex(32))')" | gcloud secrets create SECRET_KEY --data-file=-
printf '%s' '<contraseña BD>' | gcloud secrets create DB_PASSWORD --data-file=-
# (y ANTHROPIC_API_KEY / OPENAI_API_KEY / GEMINI_API_KEY / SMTP_CLAVE si se usan)

# 3. Construir y desplegar (desde la carpeta Raices, donde está el Dockerfile)
gcloud run deploy raices --source . --region=REGION --allow-unauthenticated \
  --add-cloudsql-instances=PROYECTO:REGION:raices-mysql \
  --set-env-vars=RAICES_ENV=production,DB_USER=raices_app,DB_NAME=raices,DB_HOST=/cloudsql/PROYECTO:REGION:raices-mysql,PROVEEDOR_IA=ninguno,SITIO_URL=https://TU-DOMINIO \
  --set-secrets=SECRET_KEY=SECRET_KEY:latest,DB_PASSWORD=DB_PASSWORD:latest \
  --max-instances=2
```
4. **Crear las tablas**: ejecuta una vez `flask db upgrade` (con la migración generada y revisada en local) o, para la primera prueba, `flask --app app init-db`,
   desde Cloud Shell usando el Cloud SQL Auth Proxy, o como Cloud Run Job con la misma imagen. Después crea tu cuenta y asígnate el rol con `flask asignar-rol` si corresponde.
5. **Dominio y HTTPS**: Cloud Run entrega una URL `https://….run.app` con certificado administrado. Para un dominio propio, usa la asignación de dominio de Cloud Run o un balanceador; revisa la documentación vigente y sus costos antes de elegir.
6. **Variables de producción**: `RAICES_ENV=production` activa cookie `Secure`, HSTS y exige `SECRET_KEY`; `PROXY_SALTOS=1` (ya en el Dockerfile) para ver la IP real del visitante.
7. **Copias de seguridad**: la opción `--backup-start-time` activa copias automáticas diarias; prueba restaurarlas al menos una vez.

## Limitaciones a tener presentes
- Los límites por IP y de intentos de login viven en memoria de cada instancia; con `--max-instances=2` pueden duplicarse. El tope diario de IA **sí** es global (base de datos).
- Con gunicorn `--workers 1 --threads 4`, el límite por IP es consistente dentro de una instancia.
- Si activas la IA, el texto de los usuarios sale hacia el proveedor: el aviso de privacidad ya lo explica.
- Correo: sin SMTP configurado en producción, la recuperación de contraseña **no envía nada** (se registra un error). Configura `SMTP_*`.
