-- =====================================================================
-- Raíces · estructura COMPLETA de la base de datos (MySQL 8.0.16 o superior)
-- Equivale a SRC/models.py. Para una base NUEVA y vacía.
--
--   Uso (consola de MySQL):
--     CREATE DATABASE raices CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
--     USE raices;
--     SOURCE C:/ruta/al/proyecto/docs/mysql/schema_completo.sql;
--
-- No inserta vocabulario ni traducciones: solo la variante inicial (la misma que crea `flask init-db`).
-- Si ya tienes tablas de una versión anterior, NO uses este archivo: usa migracion_desde_v1.sql.
-- =====================================================================
SET NAMES utf8mb4;

-- ---------- Cuentas ----------
CREATE TABLE usuarios (
  id INT NOT NULL AUTO_INCREMENT,
  nombre VARCHAR(80) NOT NULL,
  correo VARCHAR(254) NOT NULL,
  contrasena_hash VARCHAR(255) NOT NULL,
  rol VARCHAR(10) NOT NULL,
  activo TINYINT(1) NOT NULL,
  creado_en DATETIME NOT NULL,
  ultimo_acceso DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_usuarios_correo (correo),
  CONSTRAINT ck_usuario_rol CHECK (rol IN ('usuario', 'hablante'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE perfiles (
  usuario_id INT NOT NULL,
  pronombres VARCHAR(30) NOT NULL,
  biografia VARCHAR(300) NOT NULL,
  instagram VARCHAR(255) NOT NULL,
  facebook VARCHAR(255) NOT NULL,
  tiktok VARCHAR(255) NOT NULL,
  youtube VARCHAR(255) NOT NULL,
  sitio_web VARCHAR(255) NOT NULL,
  PRIMARY KEY (usuario_id),
  CONSTRAINT fk_perfil_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE tokens_recuperacion (
  id INT NOT NULL AUTO_INCREMENT,
  usuario_id INT NOT NULL,
  token_hash VARCHAR(64) NOT NULL,
  expira DATETIME NOT NULL,
  usado TINYINT(1) NOT NULL,
  creado_en DATETIME NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_token_hash (token_hash),
  KEY ix_token_usuario (usuario_id),
  CONSTRAINT fk_token_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Contenido lingüístico ----------
CREATE TABLE variantes (
  id INT NOT NULL AUTO_INCREMENT,
  codigo VARCHAR(10) NOT NULL,
  nombre VARCHAR(120) NOT NULL,
  region VARCHAR(120) NULL,
  activa TINYINT(1) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_variantes_codigo (codigo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE hablantes (
  id INT NOT NULL AUTO_INCREMENT,
  nombre_publico VARCHAR(120) NOT NULL,
  variante_id INT NOT NULL,
  usuario_id INT NULL,
  consentimiento_creditos TINYINT(1) NOT NULL,
  consentimiento_audio TINYINT(1) NOT NULL,
  consentimiento_fecha DATETIME NULL,
  notas TEXT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_hablantes_usuario (usuario_id),
  CONSTRAINT fk_hablante_variante FOREIGN KEY (variante_id) REFERENCES variantes (id),
  CONSTRAINT fk_hablante_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE fuentes (
  id INT NOT NULL AUTO_INCREMENT,
  titulo VARCHAR(255) NOT NULL,
  autores VARCHAR(255) NULL,
  anio INT NULL,
  tipo VARCHAR(20) NOT NULL,
  url VARCHAR(500) NULL,
  licencia VARCHAR(255) NULL,
  permiso_estado VARCHAR(20) NOT NULL,
  variante_id INT NULL,
  notas TEXT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_fuente_variante FOREIGN KEY (variante_id) REFERENCES variantes (id),
  CONSTRAINT ck_fuente_tipo CHECK (tipo IN ('diccionario', 'gramatica', 'corpus', 'hablante', 'otro')),
  CONSTRAINT ck_fuente_permiso CHECK (permiso_estado IN ('sin_solicitar', 'solicitado', 'autorizado', 'denegado', 'no_aplica'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE categorias (
  id INT NOT NULL AUTO_INCREMENT,
  clave VARCHAR(40) NOT NULL,
  nombre VARCHAR(80) NOT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_categorias_clave (clave)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE traducciones (
  id INT NOT NULL AUTO_INCREMENT,
  variante_id INT NOT NULL,
  tipo VARCHAR(10) NOT NULL,
  texto_es VARCHAR(500) NOT NULL,
  texto_es_norm VARCHAR(500) NOT NULL,
  texto_mixteco VARCHAR(500) COLLATE utf8mb4_bin NOT NULL,   -- binaria: tonos, acentos y saltillo cuentan
  categoria_id INT NULL,
  ejemplo_de_id INT NULL,
  estado VARCHAR(12) NOT NULL,
  origen VARCHAR(20) NOT NULL,
  fuente_id INT NULL,
  verificada_por_id INT NULL,
  verificada_en DATETIME NULL,
  aportada_por_id INT NULL,
  creada_en DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_trad_busqueda (variante_id, estado, texto_es_norm),
  KEY ix_trad_aportante (aportada_por_id),
  CONSTRAINT fk_trad_variante FOREIGN KEY (variante_id) REFERENCES variantes (id),
  CONSTRAINT fk_trad_categoria FOREIGN KEY (categoria_id) REFERENCES categorias (id),
  CONSTRAINT fk_trad_ejemplo_de FOREIGN KEY (ejemplo_de_id) REFERENCES traducciones (id),
  CONSTRAINT fk_trad_fuente FOREIGN KEY (fuente_id) REFERENCES fuentes (id),
  CONSTRAINT fk_trad_verificada_por FOREIGN KEY (verificada_por_id) REFERENCES hablantes (id),
  CONSTRAINT fk_trad_aportada_por FOREIGN KEY (aportada_por_id) REFERENCES usuarios (id) ON DELETE SET NULL,
  CONSTRAINT ck_trad_tipo CHECK (tipo IN ('palabra', 'frase', 'oracion')),
  CONSTRAINT ck_trad_estado CHECK (estado IN ('pendiente', 'verificada', 'rechazada')),
  CONSTRAINT ck_trad_origen CHECK (origen IN ('fuente_publicada', 'hablante', 'usuario', 'ia')),
  CONSTRAINT ck_verificada_con_respaldo CHECK (estado <> 'verificada' OR fuente_id IS NOT NULL
        OR (verificada_por_id IS NOT NULL AND verificada_en IS NOT NULL)),
  CONSTRAINT ck_ia_verificada_por_persona CHECK (origen <> 'ia' OR estado <> 'verificada' OR verificada_por_id IS NOT NULL)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE validaciones (
  id INT NOT NULL AUTO_INCREMENT,
  traduccion_id INT NOT NULL,
  hablante_id INT NOT NULL,
  resultado VARCHAR(12) NOT NULL,
  texto_mixteco_propuesto VARCHAR(500) COLLATE utf8mb4_bin NULL,
  comentario TEXT NULL,
  fecha DATETIME NOT NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_validacion_traduccion FOREIGN KEY (traduccion_id) REFERENCES traducciones (id),
  CONSTRAINT fk_validacion_hablante FOREIGN KEY (hablante_id) REFERENCES hablantes (id),
  CONSTRAINT ck_validacion_resultado CHECK (resultado IN ('aprobada', 'corregida', 'rechazada'))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE audios (
  id INT NOT NULL AUTO_INCREMENT,
  traduccion_id INT NOT NULL,
  ruta_archivo VARCHAR(255) NOT NULL,
  origen VARCHAR(12) NOT NULL,
  hablante_id INT NULL,
  autorizado TINYINT(1) NOT NULL,
  estado VARCHAR(12) NOT NULL,
  creado_en DATETIME NOT NULL,
  PRIMARY KEY (id),
  KEY ix_audio_traduccion (traduccion_id),
  CONSTRAINT fk_audio_traduccion FOREIGN KEY (traduccion_id) REFERENCES traducciones (id),
  CONSTRAINT fk_audio_hablante FOREIGN KEY (hablante_id) REFERENCES hablantes (id),
  CONSTRAINT ck_audio_origen CHECK (origen IN ('grabacion', 'tts')),
  CONSTRAINT ck_audio_estado CHECK (estado IN ('pendiente', 'aprobado', 'rechazado')),
  CONSTRAINT ck_audio_grabacion_autorizada CHECK (origen <> 'grabacion' OR (hablante_id IS NOT NULL AND autorizado = 1))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Control de gasto de la IA ----------
CREATE TABLE uso_ia (
  fecha DATE NOT NULL,
  llamadas INT NOT NULL,
  PRIMARY KEY (fecha)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ---------- Variante inicial (configuración, no es vocabulario) ----------
INSERT INTO variantes (codigo, nombre, region, activa)
VALUES ('mxb', 'Mixteco de Tezoatlán', 'Tezoatlán, Oaxaca', 1);
