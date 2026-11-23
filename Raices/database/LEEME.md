# Base de datos de Raíces

| Archivo | Para qué sirve |
|---|---|
| `schema_completo.sql` | **La base de datos.** Crea todas las tablas (MySQL 8.0.16+) y la variante inicial `mxb`. Para una base nueva y vacía. |
| `migracion_desde_v1.sql` | Solo si ya tienes tablas de una versión anterior y quieres conservar sus datos. Repetible; no borra nada. |

La base empieza **sin vocabulario ni traducciones** a propósito: esos datos los carga y valida la persona hablante.
(Con el SQLite de desarrollo no necesitas nada de esto: las tablas se crean solas al arrancar.)

## Crear la base en MySQL (Windows)
1. Abre una terminal y entra a MySQL: `mysql -u root -p`
2. Dentro de MySQL:
   ```sql
   CREATE DATABASE raices CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   USE raices;
   SOURCE C:/ruta/a/tu/proyecto/database/schema_completo.sql;
   ```
   (usa barras `/` en la ruta, aunque sea Windows)
3. En `.env`: `DB_USER`, `DB_PASSWORD`, `DB_HOST=localhost`, `DB_PORT=3306`, `DB_NAME=raices`.
4. Comprueba: `cd SRC` → `flask --app app revisar-bd` debe decir que coincide con los modelos.

Si prefieres no usar el `.sql`: crea la base vacía (paso 2, sin `SOURCE`) y ejecuta `flask --app app init-db`.
Ver el README para el caso de error `1054 Unknown column`.
