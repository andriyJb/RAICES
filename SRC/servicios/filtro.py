"""Filtro de respaldo: decide si una propuesta de IA es razonable para mostrarse como «automática».

Qué hace (y qué NO hace)
- NO exige que cada palabra esté en el diccionario: con poco vocabulario verificado eso bloquearía
  casi todo. Tampoco convierte nada en «verificado»: pasar el filtro solo permite mostrar la
  propuesta con el aviso de que no está verificada.
- Rechaza lo que claramente no es una traducción usable: vacía, con confianza «baja», igual al
  texto original, desproporcionada, con marcado/enlaces/saltos de línea, con fragmentos de las
  instrucciones del sistema, o con caracteres que no pertenecen a la escritura del mixteco.
"""
import re

# Letras (con tonos combinados), números, espacios, saltillo y puntuación habitual.
_PERMITIDO = re.compile(r"[\w\s'\-.,;:!?¿¡()«»\"̀-ͯ]+")
_PROHIBIDO = re.compile(r"https?://|www\.|<|>|[{}\[\]]|```|\n|\r", re.IGNORECASE)
# Frases que solo aparecerían si el modelo repite sus instrucciones o la inyección funcionó.
_FUGAS = ("eres un asistente", "reglas", "texto a traducir", "contexto (entradas", "ignora lo anterior",
          "instrucciones del sistema", "as an ai", "como modelo de lenguaje")

RAZON_MIN, RAZON_MAX = 0.25, 6.0   # largo de la traducción respecto al texto original


def evaluar(texto, propuesta, contexto=None, estricto=True):
    """Devuelve (aceptada, motivo). El motivo sirve para pruebas y para depurar."""
    t = (propuesta.traduccion or "").strip()
    if not t:
        return False, "sin traducción"
    if estricto and propuesta.confianza == "baja":
        return False, "el modelo declaró confianza baja"
    if _PROHIBIDO.search(t):
        return False, "contiene marcado, enlaces o saltos de línea"
    if not _PERMITIDO.fullmatch(t):
        return False, "contiene caracteres ajenos a la escritura"
    if t.casefold() == texto.strip().casefold():
        return False, "es igual al texto original"
    minusculas = t.casefold()
    if any(f in minusculas for f in _FUGAS):
        return False, "repite instrucciones del sistema"
    # Frases muy cortas (una o dos palabras) pueden ser mucho más largas o cortas; solo se vigila lo extremo.
    razon = len(t) / max(len(texto.strip()), 1)
    if razon > RAZON_MAX or (len(texto.strip()) > 20 and razon < RAZON_MIN):
        return False, "longitud desproporcionada"
    return True, "ok"


def filtro_respaldo(texto, propuesta, contexto):
    return evaluar(texto, propuesta, contexto)[0]


def crear_filtro(estricto=True):
    """Devuelve la función de filtro. Con estricto=False se aceptan propuestas de confianza «baja»
    (siguen mostrándose como automáticas y sin verificar)."""
    def filtro(texto, propuesta, contexto):
        return evaluar(texto, propuesta, contexto, estricto)[0]
    return filtro
