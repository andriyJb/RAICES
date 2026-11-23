"""Limpieza, validación y normalización de texto (español y mixteco)."""
import re
import unicodedata

_PUNTUACION = re.compile(r"[^\w\s]", re.UNICODE)
# Se quitan los acentos del español pero se conserva la ñ (ano y año son palabras distintas).
_SIN_ACENTOS = str.maketrans("áéíóúü", "aeiouu")

# Carácter único para el saltillo. DECISIÓN PENDIENTE con la persona hablante
# (ver docs/proceso_validacion.md): si elige otro, solo se cambia aquí.
SALTILLO = "'"
_VARIANTES_SALTILLO = "’ʼ´`ꞌ‘′"


def validar_entrada(texto, max_caracteres):
    """Devuelve (texto_limpio, None) o (None, mensaje_de_error)."""
    if not isinstance(texto, str):
        return None, "El texto no es válido."
    limpio = unicodedata.normalize("NFC", texto)
    # Quita caracteres de control e invisibles; conserva letras, números y signos.
    limpio = "".join(c for c in limpio if c.isprintable() or c in "\n\t")
    limpio = " ".join(limpio.split())
    if not limpio:
        return None, "Escribe una palabra, frase u oración."
    if len(limpio) > max_caracteres:
        return None, f"El texto no puede superar {max_caracteres} caracteres."
    return limpio, None


def normalizar_es(texto):
    """Forma de comparación: minúsculas, sin acentos (salvo ñ), sin puntuación, espacios simples."""
    minusculas = unicodedata.normalize("NFC", texto).casefold().translate(_SIN_ACENTOS)
    return " ".join(_PUNTUACION.sub(" ", minusculas).split())


def limpiar_mixteco(texto):
    """Texto en mixteco: Unicode NFC, saltillo unificado y espacios simples.

    No cambia mayúsculas ni quita tonos: esa escritura la decide el hablante.
    """
    valor = unicodedata.normalize("NFC", texto or "")
    for variante in _VARIANTES_SALTILLO:
        valor = valor.replace(variante, SALTILLO)
    valor = "".join(c for c in valor if c.isprintable())
    return " ".join(valor.split())
