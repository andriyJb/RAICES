"""Modelos de base de datos de Raíces (SQLAlchemy).

Mapa de tablas (las flechas indican "pertenece a"):

  CUENTAS          usuarios ← perfiles (1 a 1) · usuarios ← tokens_recuperacion
  LINGÜÍSTICO      variantes ← traducciones → categorias
                   traducciones → fuentes (de dónde sale)
                   traducciones → hablantes (quién la revisó)
                   traducciones ← validaciones (historial de revisiones)
                   traducciones ← audios
                   traducciones → traducciones (una oración puede ser "ejemplo de" una palabra)
  hablantes → usuarios (opcional: un hablante puede tener una cuenta)

Reglas importantes
- Todo contenido lingüístico pertenece a una VARIANTE (variante_id): nunca se mezclan.
- Una traducción solo puede quedar "verificada" si tiene respaldo: una fuente publicada
  o la revisión de un hablante con fecha (restricción ck_verificada_con_respaldo).
- Una propuesta de IA no se guarda como verificada. Los aportes de usuarios quedan "pendiente".
- Texto en mixteco: en MySQL se compara con collation binaria, así los tonos, acentos
  y el saltillo cuentan como diferencias reales.

Requiere MySQL 8.0.16 o superior (para que se apliquen las restricciones CHECK).
"""
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Index

from extensions import db


def _ahora():
    return datetime.now(timezone.utc)


def _tabla(*elementos):
    """Argumentos de tabla: restricciones + utf8mb4 (acentos, ñ y saltillo en MySQL)."""
    return (*elementos, {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"})


# Texto en mixteco con collation binaria en MySQL (ver nota arriba).
TEXTO_MIXTECO = db.String(500).with_variant(db.String(500, collation="utf8mb4_bin"), "mysql")

ROLES = ("usuario", "hablante")
TIPOS_TEXTO = ("palabra", "frase", "oracion")
ESTADOS_TRADUCCION = ("pendiente", "verificada", "rechazada")
ORIGENES = ("fuente_publicada", "hablante", "usuario", "ia")
TIPOS_FUENTE = ("diccionario", "gramatica", "corpus", "hablante", "otro")
PERMISOS = ("sin_solicitar", "solicitado", "autorizado", "denegado", "no_aplica")
RESULTADOS_VALIDACION = ("aprobada", "corregida", "rechazada")


def _en(columna, valores):
    return f"{columna} IN ({', '.join(repr(v) for v in valores)})"


# ---------------------------------------------------------------------------
# Cuentas
# ---------------------------------------------------------------------------
class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    correo = db.Column(db.String(254), nullable=False, unique=True)
    contrasena_hash = db.Column(db.String(255), nullable=False)  # nunca la contraseña en claro
    rol = db.Column(db.String(10), nullable=False, default="usuario")
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=_ahora)
    ultimo_acceso = db.Column(db.DateTime(timezone=True))

    perfil = db.relationship("Perfil", uselist=False, back_populates="usuario",
                             cascade="all, delete-orphan")

    __table_args__ = _tabla(CheckConstraint(_en("rol", ROLES), name="ck_usuario_rol"))


class Perfil(db.Model):
    """Datos opcionales que la persona decide mostrar (antes vivían en perfiles.json)."""

    __tablename__ = "perfiles"

    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    pronombres = db.Column(db.String(30), nullable=False, default="")
    biografia = db.Column(db.String(300), nullable=False, default="")
    instagram = db.Column(db.String(255), nullable=False, default="")
    facebook = db.Column(db.String(255), nullable=False, default="")
    tiktok = db.Column(db.String(255), nullable=False, default="")
    youtube = db.Column(db.String(255), nullable=False, default="")
    sitio_web = db.Column(db.String(255), nullable=False, default="")

    usuario = db.relationship("Usuario", back_populates="perfil")

    __table_args__ = _tabla()


class TokenRecuperacion(db.Model):
    """Enlace de recuperación de contraseña. Solo se guarda el hash del token."""

    __tablename__ = "tokens_recuperacion"

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False)
    token_hash = db.Column(db.String(64), nullable=False, unique=True)
    expira = db.Column(db.DateTime(timezone=True), nullable=False)
    usado = db.Column(db.Boolean, nullable=False, default=False)
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=_ahora)

    __table_args__ = _tabla(Index("ix_token_usuario", "usuario_id"))


# ---------------------------------------------------------------------------
# Contenido lingüístico
# ---------------------------------------------------------------------------
class Variante(db.Model):
    __tablename__ = "variantes"

    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(10), nullable=False, unique=True)  # ISO 639-3, p. ej. mxb
    nombre = db.Column(db.String(120), nullable=False)
    region = db.Column(db.String(120))
    activa = db.Column(db.Boolean, nullable=False, default=True)  # solo las activas se muestran

    __table_args__ = _tabla()


class Hablante(db.Model):
    """Persona que valida o graba. Solo se guarda lo necesario y con su consentimiento."""

    __tablename__ = "hablantes"

    id = db.Column(db.Integer, primary_key=True)
    nombre_publico = db.Column(db.String(120), nullable=False)  # nombre o seudónimo para créditos
    variante_id = db.Column(db.Integer, db.ForeignKey("variantes.id"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"), unique=True)
    consentimiento_creditos = db.Column(db.Boolean, nullable=False, default=False)
    consentimiento_audio = db.Column(db.Boolean, nullable=False, default=False)
    consentimiento_fecha = db.Column(db.DateTime(timezone=True))
    notas = db.Column(db.Text)

    __table_args__ = _tabla()


class Fuente(db.Model):
    """Diccionario, gramática o corpus consultado, con el estado de su permiso de uso."""

    __tablename__ = "fuentes"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(255), nullable=False)
    autores = db.Column(db.String(255))
    anio = db.Column(db.Integer)
    tipo = db.Column(db.String(20), nullable=False)
    url = db.Column(db.String(500))
    licencia = db.Column(db.String(255))
    permiso_estado = db.Column(db.String(20), nullable=False, default="sin_solicitar")
    variante_id = db.Column(db.Integer, db.ForeignKey("variantes.id"))
    notas = db.Column(db.Text)

    __table_args__ = _tabla(
        CheckConstraint(_en("tipo", TIPOS_FUENTE), name="ck_fuente_tipo"),
        CheckConstraint(_en("permiso_estado", PERMISOS), name="ck_fuente_permiso"),
    )


class Categoria(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    clave = db.Column(db.String(40), nullable=False, unique=True)
    nombre = db.Column(db.String(80), nullable=False)

    __table_args__ = _tabla()


class Traduccion(db.Model):
    """Palabra, frase u oración en español con su traducción a una variante."""

    __tablename__ = "traducciones"

    id = db.Column(db.Integer, primary_key=True)
    variante_id = db.Column(db.Integer, db.ForeignKey("variantes.id"), nullable=False)
    tipo = db.Column(db.String(10), nullable=False)
    texto_es = db.Column(db.String(500), nullable=False)
    texto_es_norm = db.Column(db.String(500), nullable=False)  # para buscar (ver servicios/texto.py)
    texto_mixteco = db.Column(TEXTO_MIXTECO, nullable=False)
    categoria_id = db.Column(db.Integer, db.ForeignKey("categorias.id"))
    ejemplo_de_id = db.Column(db.Integer, db.ForeignKey("traducciones.id"))  # oración que ilustra una palabra
    estado = db.Column(db.String(12), nullable=False, default="pendiente")
    origen = db.Column(db.String(20), nullable=False)
    fuente_id = db.Column(db.Integer, db.ForeignKey("fuentes.id"))
    verificada_por_id = db.Column(db.Integer, db.ForeignKey("hablantes.id"))
    verificada_en = db.Column(db.DateTime(timezone=True))
    aportada_por_id = db.Column(db.Integer, db.ForeignKey("usuarios.id", ondelete="SET NULL"))
    creada_en = db.Column(db.DateTime(timezone=True), nullable=False, default=_ahora)

    variante = db.relationship("Variante")
    categoria = db.relationship("Categoria")
    fuente = db.relationship("Fuente")
    verificada_por = db.relationship("Hablante")

    __table_args__ = _tabla(
        CheckConstraint(_en("tipo", TIPOS_TEXTO), name="ck_trad_tipo"),
        CheckConstraint(_en("estado", ESTADOS_TRADUCCION), name="ck_trad_estado"),
        CheckConstraint(_en("origen", ORIGENES), name="ck_trad_origen"),
        # Una traducción "verificada" necesita una fuente o un hablante con fecha de revisión.
        CheckConstraint(
            "estado <> 'verificada' OR fuente_id IS NOT NULL "
            "OR (verificada_por_id IS NOT NULL AND verificada_en IS NOT NULL)",
            name="ck_verificada_con_respaldo",
        ),
        # Una propuesta de IA nunca queda verificada sin pasar por la revisión de una persona.
        CheckConstraint("origen <> 'ia' OR estado <> 'verificada' OR verificada_por_id IS NOT NULL",
                        name="ck_ia_verificada_por_persona"),
        Index("ix_trad_busqueda", "variante_id", "estado", "texto_es_norm"),
        Index("ix_trad_aportante", "aportada_por_id"),
    )


class Validacion(db.Model):
    """Historial de revisiones: qué se revisó, quién, cuándo y con qué resultado."""

    __tablename__ = "validaciones"

    id = db.Column(db.Integer, primary_key=True)
    traduccion_id = db.Column(db.Integer, db.ForeignKey("traducciones.id"), nullable=False)
    hablante_id = db.Column(db.Integer, db.ForeignKey("hablantes.id"), nullable=False)
    resultado = db.Column(db.String(12), nullable=False)
    texto_mixteco_propuesto = db.Column(TEXTO_MIXTECO)  # si el hablante corrige la escritura
    comentario = db.Column(db.Text)
    fecha = db.Column(db.DateTime(timezone=True), nullable=False, default=_ahora)

    __table_args__ = _tabla(
        CheckConstraint(_en("resultado", RESULTADOS_VALIDACION), name="ck_validacion_resultado"),
    )


class UsoIA(db.Model):
    """Llamadas diarias al proveedor de IA. Un solo renglón por día (tope global de gasto).

    Está en la base de datos y no en memoria para que el tope valga aunque haya
    varias instancias de la aplicación (por ejemplo, en Cloud Run).
    """

    __tablename__ = "uso_ia"

    fecha = db.Column(db.Date, primary_key=True)
    llamadas = db.Column(db.Integer, nullable=False, default=0)

    __table_args__ = _tabla()


class Audio(db.Model):
    """Pronunciación. Una grabación exige hablante y autorización expresa.

    El botón de audio solo se muestra si existe un audio aprobado y autorizado.
    """

    __tablename__ = "audios"

    id = db.Column(db.Integer, primary_key=True)
    traduccion_id = db.Column(db.Integer, db.ForeignKey("traducciones.id"), nullable=False)
    ruta_archivo = db.Column(db.String(255), nullable=False)  # relativa a la carpeta de audios
    origen = db.Column(db.String(12), nullable=False)  # grabacion | tts
    hablante_id = db.Column(db.Integer, db.ForeignKey("hablantes.id"))
    autorizado = db.Column(db.Boolean, nullable=False, default=False)
    estado = db.Column(db.String(12), nullable=False, default="pendiente")
    creado_en = db.Column(db.DateTime(timezone=True), nullable=False, default=_ahora)

    __table_args__ = _tabla(
        CheckConstraint(_en("origen", ("grabacion", "tts")), name="ck_audio_origen"),
        CheckConstraint(_en("estado", ("pendiente", "aprobado", "rechazado")), name="ck_audio_estado"),
        CheckConstraint(
            "origen <> 'grabacion' OR (hablante_id IS NOT NULL AND autorizado = 1)",
            name="ck_audio_grabacion_autorizada",
        ),
        Index("ix_audio_traduccion", "traduccion_id"),
    )
