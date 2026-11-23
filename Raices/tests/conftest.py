"""Configuración de pruebas.

Si SQLAlchemy / Flask-SQLAlchemy no están instalados, se sustituyen por maquetas SOLO para poder
importar la app. Las pruebas de rutas usan un repositorio en memoria (fakes.py); las consultas SQL
reales se prueban en test_bd.py, que se omite automáticamente si falta SQLAlchemy.
"""
import sys
from unittest.mock import MagicMock

import pytest

try:
    import flask_sqlalchemy  # noqa: F401
    import sqlalchemy  # noqa: F401
    DEPENDENCIAS_REALES = True
except ImportError:
    DEPENDENCIAS_REALES = False
    excepciones = MagicMock()
    excepciones.SQLAlchemyError = type("SQLAlchemyError", (Exception,), {})
    sys.modules["flask_sqlalchemy"] = MagicMock()
    sys.modules["sqlalchemy"] = MagicMock()
    sys.modules["sqlalchemy.exc"] = excepciones

from fakes import RepoFalso  # noqa: E402

CONFIG_BASE = {"TESTING": True, "SECRET_KEY": "clave-de-prueba", "LIMITE_SOLICITUDES": 100,
               "PROVEEDOR_IA": "ninguno", "SMTP_HOST": ""}


@pytest.fixture
def repo():
    return RepoFalso()


@pytest.fixture
def app(repo):
    from app import create_app
    return create_app(dict(CONFIG_BASE), repo=repo)


@pytest.fixture
def cliente(app):
    return app.test_client()


def token(cliente, ruta="/login"):
    """Obtiene el token CSRF de la sesión del cliente (lo expone el campo oculto de la página)."""
    import re
    html = cliente.get(ruta).get_data(as_text=True)
    return re.search(r'(?:name="csrf" value|data-csrf)="([^"]+)"', html).group(1)


@pytest.fixture
def csrf(cliente):
    return lambda ruta="/login": token(cliente, ruta)
