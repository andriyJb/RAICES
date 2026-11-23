-- =====================================================================
-- Raíces · migración de una base creada con la versión ANTERIOR (v1) a la estructura actual.
-- MySQL 8.0.16+. Es REPETIBLE: cada paso comprueba antes si ya está hecho y no borra datos.
--
-- Corrige errores como:  (1054, "Unknown column 'traducciones.aportada_por_id' in 'field list'")
-- Lo que añade a las tablas antiguas (las tablas NUEVAS —usuarios, perfiles, tokens_recuperacion, uso_ia—
-- ya las crea `flask --app app init-db`):
--   traducciones.aportada_por_id (+ llave foránea e índice) · hablantes.usuario_id (+ llave foránea, único)
--   audios: índice ix_audio_traduccion · traducciones: origen permite 'usuario' y nueva restricción de IA
--
-- Orden:  1) haz una copia (mysqldump)  2) flask --app app init-db  3) ejecuta este archivo  4) flask --app app revisar-bd
--   mysql -u USUARIO -p raices < database/migracion_desde_v1.sql
-- =====================================================================
SET NAMES utf8mb4;

-- traducciones.aportada_por_id
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'traducciones' AND COLUMN_NAME = 'aportada_por_id') AS t);
SET @sql = IF(@falta, 'ALTER TABLE traducciones ADD COLUMN aportada_por_id INT NULL', 'SELECT ''ya estaba: traducciones.aportada_por_id'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- FK fk_trad_aportada_por
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'traducciones' AND CONSTRAINT_NAME = 'fk_trad_aportada_por') AS t);
SET @sql = IF(@falta, 'ALTER TABLE traducciones ADD CONSTRAINT fk_trad_aportada_por FOREIGN KEY (aportada_por_id) REFERENCES usuarios (id) ON DELETE SET NULL', 'SELECT ''ya estaba: FK fk_trad_aportada_por'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- índice ix_trad_aportante
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'traducciones' AND INDEX_NAME = 'ix_trad_aportante') AS t);
SET @sql = IF(@falta, 'ALTER TABLE traducciones ADD INDEX ix_trad_aportante (aportada_por_id)', 'SELECT ''ya estaba: índice ix_trad_aportante'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- hablantes.usuario_id
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hablantes' AND COLUMN_NAME = 'usuario_id') AS t);
SET @sql = IF(@falta, 'ALTER TABLE hablantes ADD COLUMN usuario_id INT NULL', 'SELECT ''ya estaba: hablantes.usuario_id'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- FK fk_hablante_usuario
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hablantes' AND CONSTRAINT_NAME = 'fk_hablante_usuario') AS t);
SET @sql = IF(@falta, 'ALTER TABLE hablantes ADD CONSTRAINT fk_hablante_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL', 'SELECT ''ya estaba: FK fk_hablante_usuario'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- único uq_hablantes_usuario
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'hablantes' AND INDEX_NAME = 'uq_hablantes_usuario') AS t);
SET @sql = IF(@falta, 'ALTER TABLE hablantes ADD UNIQUE KEY uq_hablantes_usuario (usuario_id)', 'SELECT ''ya estaba: único uq_hablantes_usuario'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- índice ix_audio_traduccion
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'audios' AND INDEX_NAME = 'ix_audio_traduccion') AS t);
SET @sql = IF(@falta, 'ALTER TABLE audios ADD INDEX ix_audio_traduccion (traduccion_id)', 'SELECT ''ya estaba: índice ix_audio_traduccion'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- restricción ck_trad_origen debe permitir 'usuario'
SET @ok = (SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
           WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = 'ck_trad_origen' AND CHECK_CLAUSE LIKE '%usuario%');
SET @hay = (SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
            WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = 'ck_trad_origen');
SET @sql = IF(@ok > 0, 'SELECT ''ya estaba: ck_trad_origen'' AS info',
              IF(@hay > 0, 'ALTER TABLE traducciones DROP CHECK ck_trad_origen', 'SELECT ''ck_trad_origen no existía'' AS info'));
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;
SET @ok = (SELECT COUNT(*) FROM information_schema.CHECK_CONSTRAINTS
           WHERE CONSTRAINT_SCHEMA = DATABASE() AND CONSTRAINT_NAME = 'ck_trad_origen');
SET @sql = IF(@ok = 0, 'ALTER TABLE traducciones ADD CONSTRAINT ck_trad_origen CHECK (origen IN (''fuente_publicada'', ''hablante'', ''usuario'', ''ia''))',
              'SELECT ''ck_trad_origen en orden'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

-- restricción ck_ia_verificada_por_persona
SET @falta = (SELECT COUNT(*) = 0 FROM (SELECT 1 FROM information_schema.TABLE_CONSTRAINTS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'traducciones' AND CONSTRAINT_NAME = 'ck_ia_verificada_por_persona') AS t);
SET @sql = IF(@falta, "ALTER TABLE traducciones ADD CONSTRAINT ck_ia_verificada_por_persona CHECK (origen <> 'ia' OR estado <> 'verificada' OR verificada_por_id IS NOT NULL)", 'SELECT ''ya estaba: restricción ck_ia_verificada_por_persona'' AS info');
PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;

SELECT 'Migración terminada' AS resultado;
