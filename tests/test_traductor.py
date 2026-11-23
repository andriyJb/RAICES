import pytest

from fakes import RepoFalso, hallada
from servicios.filtro import filtro_respaldo
from servicios.tipos import ErrorProveedor, Propuesta
from servicios.traductor import (AUTOMATICA, AVISO_AUTOMATICA, INSUFICIENTE, VERIFICADA, Traductor)

VARIANTE = {"codigo": "mxb", "nombre": "Mixteco de Tezoatlán"}


class IAFalsa:
    """Doble de prueba del proveedor: NO es una llamada real a ninguna IA."""
    def __init__(self, propuesta=None, error=None):
        self.propuesta, self.error, self.llamadas, self.contextos = propuesta, error, 0, []

    def proponer(self, texto, variante, contexto):
        self.llamadas += 1
        self.contextos.append(contexto)
        if self.error:
            raise self.error
        return self.propuesta


def _prop(t="propuesta prueba", c="media"):
    return Propuesta(traduccion=t, confianza=c)


def test_coincidencia_completa_es_verificada_con_procedencia_y_audio():
    repo = RepoFalso()
    repo.verificadas["texto uno"] = [hallada("[A]", categoria="cat", procedencia="Fuente: X", audio_id=7), hallada("[B]")]
    r = Traductor(repo).traducir("Texto UNO.", VARIANTE)
    assert r.estado == VERIFICADA and r.traduccion == "[A]" and r.alternativas == ["[B]"]
    d = r.a_dict()
    assert d["audio_url"] == "/audio/7" and d["procedencia"] == "Fuente: X"


def test_sin_audio_no_hay_url():
    repo = RepoFalso()
    repo.verificadas["hola"] = [hallada("[A]")]
    assert Traductor(repo).traducir("hola", VARIANTE).a_dict()["audio_url"] is None


def test_oracion_no_es_verificada_porque_sus_palabras_esten_en_el_diccionario():
    repo = RepoFalso()
    repo.verificadas.update({"texto": [hallada("[A]")], "uno": [hallada("[B]")]})
    assert Traductor(repo).traducir("texto uno", VARIANTE).estado == INSUFICIENTE


def test_sin_proveedor_es_insuficiente_y_no_llama_a_nada():
    r = Traductor(RepoFalso()).traducir("algo", VARIANTE)
    assert r.estado == INSUFICIENTE and "no está activada" in r.mensaje


def test_proveedor_exige_filtro():
    with pytest.raises(ValueError):
        Traductor(RepoFalso(), IAFalsa(_prop()))


def test_propuesta_valida_es_automatica_con_aviso_nunca_verificada():
    ia = IAFalsa(_prop())
    r = Traductor(RepoFalso(), ia, filtro_respaldo, 10).traducir("buenos dias amigo", VARIANTE)
    assert r.estado == AUTOMATICA and r.mensaje == AVISO_AUTOMATICA and ia.llamadas == 1


def test_la_ia_recibe_como_contexto_las_entradas_verificadas():
    repo = RepoFalso()
    repo.verificadas["amigo"] = [hallada("[mx:amigo]")]
    ia = IAFalsa(_prop())
    Traductor(repo, ia, filtro_respaldo, 10).traducir("hola amigo mio", VARIANTE)
    assert ia.contextos[0] == [{"es": "amigo", "mixteco": "[mx:amigo]", "tipo": "palabra"}]


def test_no_se_rechaza_una_oracion_solo_porque_sus_palabras_no_esten_en_el_diccionario():
    r = Traductor(RepoFalso(), IAFalsa(_prop("oracion propuesta nueva")), filtro_respaldo, 10).traducir(
        "esta es una oracion nueva", VARIANTE)
    assert r.estado == AUTOMATICA


def test_confianza_baja_o_sin_traduccion_es_insuficiente():
    for p in (_prop(c="baja"), Propuesta(traduccion=None, motivo="no sé")):
        r = Traductor(RepoFalso(), IAFalsa(p), filtro_respaldo, 10).traducir("algo raro", VARIANTE)
        assert r.estado == INSUFICIENTE


def test_tope_diario_evita_llamar_a_la_ia():
    repo, ia = RepoFalso(), IAFalsa(_prop())
    repo.tope_alcanzado = True
    r = Traductor(repo, ia, filtro_respaldo, 10).traducir("algo", VARIANTE)
    assert r.estado == INSUFICIENTE and ia.llamadas == 0 and "límite" in r.mensaje


def test_error_del_proveedor_se_propaga_no_se_disfraza():
    t = Traductor(RepoFalso(), IAFalsa(error=ErrorProveedor("x")), filtro_respaldo, 10)
    with pytest.raises(ErrorProveedor):
        t.traducir("algo", VARIANTE)


def test_logs_distinguen_error_sin_propuesta_y_rechazo(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="raices.traductor")
    def ejecutar(prop=None, error=None):
        caplog.clear()
        try:
            Traductor(RepoFalso(), IAFalsa(prop, error), filtro_respaldo, 10).traducir("TEXTO PRIVADO", VARIANTE)
        except ErrorProveedor:
            pass
        return caplog.text
    assert "error del proveedor (código 403)" in ejecutar(error=ErrorProveedor("código 403"))
    assert "SIN propuesta" in ejecutar(Propuesta(None, "baja", motivo="no sé"))
    assert "RECHAZADA por el filtro" in ejecutar(Propuesta("<b>x</b>", "alta"))
    assert "aceptada" in ejecutar(_prop())
    assert "PRIVADO" not in caplog.text


def test_motivo_del_modelo_solo_se_registra_en_modo_depuracion(caplog):
    import logging
    caplog.set_level(logging.INFO, logger="raices.traductor")
    for depurar, esperado in ((False, False), (True, True)):
        caplog.clear()
        Traductor(RepoFalso(), IAFalsa(Propuesta(None, "baja", motivo="motivo-x")), filtro_respaldo, 10,
                  depurar=depurar).traducir("algo", VARIANTE)
        assert ("motivo-x" in caplog.text) is esperado


def test_modo_libre_acepta_confianza_baja_pero_sigue_siendo_automatica():
    from servicios.filtro import crear_filtro
    for estricto, estado in ((True, INSUFICIENTE), (False, AUTOMATICA)):
        r = Traductor(RepoFalso(), IAFalsa(_prop(c="baja")), crear_filtro(estricto), 10).traducir("buenos dias amigo", VARIANTE)
        assert r.estado == estado
    assert r.mensaje == AVISO_AUTOMATICA
