"""Tipos compartidos entre el motor de traducción, los proveedores de IA y la base de datos."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Hallada:
    """Una traducción VERIFICADA encontrada en el diccionario."""
    texto: str
    categoria: Optional[str] = None
    procedencia: str = ""
    audio_id: Optional[int] = None
    ejemplos: list = field(default_factory=list)   # [{"es": ..., "mixteco": ...}]
    tipo: Optional[str] = None


@dataclass
class Propuesta:
    """Lo que devuelve un proveedor de IA (ya interpretado). NO es una traducción verificada."""
    traduccion: Optional[str]            # None = el modelo prefirió no traducir
    confianza: str = "baja"              # alta | media | baja (la declara el propio modelo)
    palabras_sin_respaldo: list = field(default_factory=list)
    motivo: str = ""


class ErrorProveedor(Exception):
    """Falló la conexión con el proveedor de IA (red, clave, límite, respuesta inválida)."""


class CorreoDuplicado(Exception):
    """Ya existe una cuenta con ese correo."""
