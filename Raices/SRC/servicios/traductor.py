"""Motor de traducción de Raíces: diccionario verificado + IA.

Flujo de `traducir()`
1. Se busca el texto COMPLETO entre las traducciones verificadas → estado «verificada».
2. Si no hay coincidencia y hay un proveedor de IA:
   a. se reserva una llamada del tope diario (si no hay cupo, no se llama a la IA);
   b. se buscan entradas verificadas relacionadas y se envían como contexto;
   c. la propuesta pasa por el filtro de respaldo → «automática» (sin verificar) o «insuficiente».
3. Si no hay proveedor → «insuficiente», con un mensaje honesto.

Regla de oro: que algunas palabras de una oración estén verificadas NO hace verificada a la
oración. Y nada que venga de la IA se muestra jamás como verificado.

Los errores del proveedor (ErrorProveedor) NO se disfrazan de «información insuficiente»:
se propagan para que la ruta avise que el servicio falló.
"""
import logging
from dataclasses import dataclass, field
from typing import Optional

from .texto import normalizar_es
from .tipos import ErrorProveedor

log = logging.getLogger("raices.traductor")   # nunca se registra el texto del usuario

VERIFICADA = "verificada"
AUTOMATICA = "automatica"
INSUFICIENTE = "insuficiente"

AVISO_AUTOMATICA = (
    "Esta traducción fue generada mediante inteligencia artificial y todavía no cuenta "
    "con una verificación confirmada por un hablante o especialista. "
    "Puede contener errores de vocabulario, escritura o significado."
)
MENSAJE_SIN_IA = (
    "Todavía no tenemos una traducción verificada para este texto, y la traducción "
    "automática no está activada en este servidor."
)
MENSAJE_SIN_INFORMACION = "No contamos con información suficiente para proponer una traducción confiable."
MENSAJE_LIMITE_IA = "Se alcanzó el límite diario de propuestas automáticas. Intenta de nuevo mañana."


@dataclass
class Resultado:
    estado: str
    variante: str
    texto_original: str
    traduccion: Optional[str] = None
    alternativas: list = field(default_factory=list)   # otras traducciones verificadas del mismo texto
    categoria: Optional[str] = None
    tipo: Optional[str] = None
    procedencia: str = ""
    ejemplos: list = field(default_factory=list)
    audio_id: Optional[int] = None
    mensaje: Optional[str] = None

    def a_dict(self):
        d = dict(self.__dict__)
        d["audio_url"] = f"/audio/{self.audio_id}" if self.audio_id else None
        d.pop("audio_id")
        return d


class Traductor:
    """`repo` ofrece buscar_verificadas, buscar_contexto y reservar_llamada_ia (ver repositorio.py)."""

    def __init__(self, repo, proveedor=None, filtro=None, limite_diario=0, depurar=False):
        if proveedor is not None and filtro is None:
            # Nunca mostrar propuestas de IA sin pasar por un filtro de respaldo.
            raise ValueError("Un proveedor de IA requiere un filtro de respaldo.")
        self._repo, self._ia, self._filtro, self._limite = repo, proveedor, filtro, limite_diario
        self._depurar = depurar    # en desarrollo, registra también el motivo que da el modelo

    @property
    def ia_activa(self):
        return self._ia is not None

    def traducir(self, texto, variante):
        """`variante` es un diccionario con al menos «codigo» y «nombre»."""
        codigo_variante = variante["codigo"]
        norm = normalizar_es(texto)
        if not norm:
            return Resultado(INSUFICIENTE, codigo_variante, texto, mensaje=MENSAJE_SIN_INFORMACION)

        halladas = self._repo.buscar_verificadas(norm, codigo_variante)
        log.info("Diccionario: %s", "coincidencia verificada" if halladas else "sin coincidencia")
        if halladas:
            principal, *otras = halladas
            return Resultado(
                VERIFICADA, codigo_variante, texto, traduccion=principal.texto,
                alternativas=[h.texto for h in otras if h.texto != principal.texto],
                categoria=principal.categoria, tipo=principal.tipo, procedencia=principal.procedencia,
                ejemplos=principal.ejemplos, audio_id=principal.audio_id)

        if self._ia is None:
            log.info("IA desactivada: resultado «insuficiente»")
            return Resultado(INSUFICIENTE, codigo_variante, texto, mensaje=MENSAJE_SIN_IA)
        if not self._repo.reservar_llamada_ia(self._limite):
            log.warning("IA no consultada: tope diario alcanzado (%s) o falla al reservar la llamada", self._limite)
            return Resultado(INSUFICIENTE, codigo_variante, texto, mensaje=MENSAJE_LIMITE_IA)

        contexto = self._repo.buscar_contexto(norm, codigo_variante)
        log.info("IA: consultando con %d entradas de contexto", len(contexto))
        try:
            propuesta = self._ia.proponer(texto, variante, contexto)
        except ErrorProveedor as e:
            log.error("IA: error del proveedor (%s)", e)
            raise
        if not propuesta.traduccion:
            log.info("IA: respuesta SIN propuesta (confianza=%s)%s", propuesta.confianza,
                     f" · motivo del modelo: {propuesta.motivo}" if self._depurar else "")
            return Resultado(INSUFICIENTE, codigo_variante, texto, mensaje=MENSAJE_SIN_INFORMACION)
        if not self._filtro(texto, propuesta, contexto):
            log.info("IA: propuesta RECHAZADA por el filtro (confianza=%s)", propuesta.confianza)
            return Resultado(INSUFICIENTE, codigo_variante, texto, mensaje=MENSAJE_SIN_INFORMACION)
        log.info("IA: propuesta aceptada como «automática» (confianza=%s)", propuesta.confianza)
        return Resultado(AUTOMATICA, codigo_variante, texto,
                         traduccion=propuesta.traduccion.strip(), mensaje=AVISO_AUTOMATICA)
