"""Configuración de Raíces.

Todo lo sensible (claves, contraseñas) viene de variables de entorno,
que en desarrollo se leen del archivo .env (nunca se sube a Git).
"""
import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _entero(nombre, defecto):
    try:
        return int(os.environ.get(nombre, defecto))
    except ValueError:
        return defecto


def _url_base_datos():
    """MySQL en producción; SQLite solo como respaldo de desarrollo."""
    url = os.environ.get("DATABASE_URL")
    if url:
        return url
    usuario = os.environ.get("DB_USER")
    if usuario:
        clave = quote_plus(os.environ.get("DB_PASSWORD", ""))
        host = os.environ.get("DB_HOST", "localhost")
        puerto = os.environ.get("DB_PORT", "3306")
        nombre = os.environ.get("DB_NAME", "raices")
        if host.startswith("/"):    # socket de Cloud SQL en Cloud Run: /cloudsql/PROYECTO:REGION:INSTANCIA
            return f"mysql+pymysql://{usuario}:{clave}@/{nombre}?unix_socket={host}&charset=utf8mb4"
        return f"mysql+pymysql://{usuario}:{clave}@{host}:{puerto}/{nombre}?charset=utf8mb4"
    return f"sqlite:///{RAIZ / 'raices_dev.db'}"


class Config:
    ENTORNO = os.environ.get("RAICES_ENV", "development")  # development | production
    SECRET_KEY = os.environ.get("SECRET_KEY")

    # Base de datos
    SQLALCHEMY_DATABASE_URI = _url_base_datos()
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Sesión (cookie firmada que guarda solo el id del usuario y el token CSRF)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ENTORNO == "production"
    PERMANENT_SESSION_LIFETIME = timedelta(days=_entero("SESION_DIAS_RECORDAR", 14))

    # Límites para evitar abusos y gastos inesperados
    MAX_CONTENT_LENGTH = 16 * 1024            # tamaño máximo de cualquier petición
    MAX_CARACTERES = _entero("MAX_CARACTERES", 200)
    LIMITE_SOLICITUDES = _entero("LIMITE_SOLICITUDES", 10)   # traducciones por IP y ventana
    VENTANA_SEGUNDOS = _entero("VENTANA_SEGUNDOS", 60)
    LIMITE_DIARIO_IA = _entero("LIMITE_DIARIO_IA", 200)      # llamadas de IA por día (global)
    PROXY_SALTOS = _entero("PROXY_SALTOS", 0)  # >0 cuando haya un proxy delante (Cloud Run: 1)

    # Intentos de inicio de sesión y de recuperación de contraseña
    MAX_INTENTOS_LOGIN = _entero("MAX_INTENTOS_LOGIN", 5)
    BLOQUEO_LOGIN_SEGUNDOS = _entero("BLOQUEO_LOGIN_SEGUNDOS", 900)
    MAX_SOLICITUDES_RECUPERACION = _entero("MAX_SOLICITUDES_RECUPERACION", 5)
    MINUTOS_TOKEN_RECUPERACION = _entero("MINUTOS_TOKEN_RECUPERACION", 30)

    # Correo (para la recuperación de contraseña). Sin SMTP, en producción se desactiva.
    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = _entero("SMTP_PORT", 587)
    SMTP_USUARIO = os.environ.get("SMTP_USUARIO", "")
    SMTP_CLAVE = os.environ.get("SMTP_CLAVE", "")
    SMTP_REMITENTE = os.environ.get("SMTP_REMITENTE", "")

    # Dirección pública del sitio (para los enlaces de los correos). Vacío = se toma de la petición.
    SITIO_URL = os.environ.get("SITIO_URL", "").rstrip("/")

    # Aportes de palabras por usuario (para evitar abuso)
    MAX_APORTES_POR_HORA = _entero("MAX_APORTES_POR_HORA", 10)

    # Motor de traducción: ninguno | anthropic | openai | gemini
    # "ninguno" = solo diccionario verificado. Con un proveedor, las claves deben estar en .env.
    # Si no se define, Gemini se activa solo cuando hay una GEMINI_API_KEY; si no, queda en "ninguno".
    PROVEEDOR_IA = (os.environ.get("PROVEEDOR_IA") or ("gemini" if os.environ.get("GEMINI_API_KEY") else "ninguno")).strip().lower()
    # IA_ESTRICTO=1: el modelo solo propone si tiene base suficiente (más honesto, a veces responde "sin propuesta").
    # IA_ESTRICTO=0: intenta siempre una propuesta (aunque sea de confianza baja); sigue marcada como NO verificada.
    IA_ESTRICTO = os.environ.get("IA_ESTRICTO", "1").strip().lower() not in ("0", "false", "no")
    IA_TIMEOUT_SEGUNDOS = _entero("IA_TIMEOUT_SEGUNDOS", 25)
    # Margen amplio: en los modelos con "razonamiento" esos tokens cuentan contra este tope y,
    # si es muy pequeño, la respuesta llega vacía.
    IA_MAX_TOKENS_SALIDA = _entero("IA_MAX_TOKENS_SALIDA", 1500)
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    # Identificadores de modelo: se pueden cambiar sin tocar el código.
    # Los tres identificadores se comprobaron en la documentación oficial el 17-nov-2026.
    # Son los modelos económicos de cada proveedor; para probar uno intermedio, solo cambia la variable.
    MODELO_ANTHROPIC = os.environ.get("MODELO_ANTHROPIC", "claude-haiku-5-5")
    MODELO_OPENAI = os.environ.get("MODELO_OPENAI", "gpt-6-luna")
    MODELO_GEMINI = os.environ.get("MODELO_GEMINI", "gemini-3.5-flash-lite")

    # Audios aprobados: carpeta FUERA de static/ (solo se sirven a través de /audio/<id>).
    AUDIO_DIR = os.environ.get("AUDIO_DIR", str(RAIZ / "audios"))

    # Variantes. La arquitectura admite varias; la v1 trabaja con una.
    VARIANTE_POR_DEFECTO = os.environ.get("VARIANTE_POR_DEFECTO", "mxb")
    VARIANTES_INICIALES = [
        {"codigo": "mxb", "nombre": "Mixteco de Tezoatlán", "region": "Tezoatlán, Oaxaca"},
    ]
