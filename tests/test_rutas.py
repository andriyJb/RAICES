import json

import pytest

from fakes import hallada
from servicios.tipos import ErrorProveedor
from conftest import CONFIG_BASE


def _traducir(cliente, csrf, texto="algo", **extra):
    return cliente.post("/api/traducir", json={"texto": texto, **extra}, headers={"X-CSRF-Token": csrf("/")})


@pytest.mark.parametrize("ruta", ["/", "/ejemplos", "/acerca", "/privacidad", "/login", "/registro", "/recuperar"])
def test_paginas_publicas_responden(cliente, ruta):
    r = cliente.get(ruta)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Prototipo académico" not in html and "[texto de demostración]" not in html


def test_ejemplos_vacio_muestra_estado_vacio_no_contenido_inventado(cliente):
    html = cliente.get("/ejemplos").get_data(as_text=True)
    assert "Aún no hay vocabulario verificado disponible para esta variante" in html


def test_ejemplos_muestra_solo_lo_que_devuelve_el_repositorio_con_filtros_y_paginacion(cliente, repo):
    repo.vocab = [dict(es=f"palabra{i}", mixteco=f"[mx{i}]", tipo="palabra", categoria=None,
                       procedencia="Revisada por una persona hablante de la variante", audio_id=None, ejemplos=[])
                  for i in range(35)]
    html = cliente.get("/ejemplos").get_data(as_text=True)
    assert "35 resultados" in html and "Página 1 de 2" in html and "palabra0" in html and "palabra34" not in html
    assert "palabra34" in cliente.get("/ejemplos?pagina=2").get_data(as_text=True)
    assert "35 resultados" not in cliente.get("/ejemplos?q=palabra3").get_data(as_text=True)
    assert cliente.get("/ejemplos?pagina=abc&tipo=xx&categoria=" + "a" * 500).status_code == 200


def test_ejemplos_boton_de_audio_solo_si_hay_audio(cliente, repo):
    base = dict(es="uno", mixteco="[m]", tipo="palabra", categoria=None, procedencia="", ejemplos=[])
    repo.vocab = [dict(base, audio_id=None)]
    assert "boton-audio" not in cliente.get("/ejemplos").get_data(as_text=True).split("<main")[1]
    repo.vocab = [dict(base, audio_id=3)]
    assert 'data-audio="/audio/3"' in cliente.get("/ejemplos").get_data(as_text=True)


def test_acerca_cuenta_real_sin_inventar(cliente, repo):
    assert "Todavía no hay traducciones verificadas" in cliente.get("/acerca").get_data(as_text=True)
    repo.verificadas["a"] = [hallada("[m]")]
    assert "<strong>1</strong>" in cliente.get("/acerca").get_data(as_text=True)


def test_privacidad_cambia_segun_ia_activa(cliente):
    assert "no se envía a ningún proveedor externo" in cliente.get("/privacidad").get_data(as_text=True)


# ---- API
def test_traducir_verificada(cliente, repo, csrf):
    repo.verificadas["texto prueba"] = [hallada("[mx:prueba]", categoria="cat")]
    r = _traducir(cliente, csrf, "Texto prueba")
    d = r.get_json()
    assert r.status_code == 200 and d["estado"] == "verificada" and d["traduccion"] == "[mx:prueba]"
    assert r.headers["Cache-Control"] == "no-store"


def test_traducir_sin_ia_es_insuficiente_con_mensaje_honesto(cliente, csrf):
    d = _traducir(cliente, csrf).get_json()
    assert d["estado"] == "insuficiente" and "no está activada" in d["mensaje"]


def test_traducir_exige_csrf(cliente):
    assert cliente.post("/api/traducir", json={"texto": "a"}).status_code == 400
    assert cliente.post("/api/traducir", json={"texto": "a"}, headers={"X-CSRF-Token": "falso"}).status_code == 400


def test_traducir_rechaza_origen_ajeno(cliente, csrf):
    r = cliente.post("/api/traducir", json={"texto": "a"},
                     headers={"X-CSRF-Token": csrf("/"), "Origin": "https://malo.example"})
    assert r.status_code == 400


@pytest.mark.parametrize("cuerpo", [{}, {"texto": ""}, {"texto": 5}, {"texto": "a" * 500}, {"texto": "hola", "variante": "zzz"},
                                    {"texto": "hola", "variante": ["x"]}])
def test_traducir_valida_entrada(cliente, csrf, cuerpo):
    r = cliente.post("/api/traducir", json=cuerpo, headers={"X-CSRF-Token": csrf("/")})
    assert r.status_code == 400 and "error" in r.get_json()


def test_traducir_json_invalido(cliente, csrf):
    r = cliente.post("/api/traducir", data="no json", headers={"X-CSRF-Token": csrf("/"), "Content-Type": "application/json"})
    assert r.status_code == 400


def test_limite_de_solicitudes_por_ip(repo):
    from app import create_app
    app = create_app({**CONFIG_BASE, "LIMITE_SOLICITUDES": 2}, repo=repo)
    c = app.test_client()
    import re
    t = re.search(r'data-csrf="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
    codigos = [c.post("/api/traducir", json={"texto": "a"}, headers={"X-CSRF-Token": t}).status_code for _ in range(3)]
    assert codigos == [200, 200, 429]


def test_peticion_enorme_413(cliente, csrf):
    r = cliente.post("/api/traducir", data="x" * 20000, headers={"X-CSRF-Token": csrf("/"), "Content-Type": "application/json"})
    assert r.status_code == 413 and "error" in r.get_json()


def test_cabeceras_de_seguridad(cliente):
    h = cliente.get("/").headers
    assert "default-src 'self'" in h["Content-Security-Policy"] and h["X-Frame-Options"] == "DENY"


def test_error_404_con_pagina_propia(cliente):
    r = cliente.get("/no-existe")
    assert r.status_code == 404 and "No encontramos la página" in r.get_data(as_text=True)


# ---- con IA configurada (HTTP falso)
class _Prov:
    def __init__(self, resultado):
        self.resultado = resultado

    def proponer(self, texto, variante, contexto):
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


@pytest.fixture
def app_ia(repo):
    from app import create_app
    from servicios.filtro import filtro_respaldo
    from servicios.traductor import Traductor
    app = create_app(dict(CONFIG_BASE), repo=repo)
    app.traductor = Traductor(repo, _Prov(None), filtro_respaldo, 5)
    return app


def test_ia_propuesta_se_marca_automatica_con_aviso(app_ia):
    from servicios.tipos import Propuesta
    app_ia.traductor._ia = _Prov(Propuesta("propuesta prueba", "media"))
    c = app_ia.test_client()
    import re
    t = re.search(r'data-csrf="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
    d = c.post("/api/traducir", json={"texto": "buenos dias amigo"}, headers={"X-CSRF-Token": t}).get_json()
    assert d["estado"] == "automatica" and "no cuenta con una verificación confirmada" in d["mensaje"]


def test_ia_caida_devuelve_502_no_insuficiente(app_ia):
    app_ia.traductor._ia = _Prov(ErrorProveedor("x"))
    c = app_ia.test_client()
    import re
    t = re.search(r'data-csrf="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
    r = c.post("/api/traducir", json={"texto": "algo"}, headers={"X-CSRF-Token": t})
    assert r.status_code == 502 and "no respondió" in r.get_json()["error"]


def test_proveedor_sin_clave_no_impide_arrancar_y_desactiva_la_ia(repo, caplog):
    from app import create_app
    app = create_app({**CONFIG_BASE, "PROVEEDOR_IA": "gemini", "GEMINI_API_KEY": ""}, repo=repo)
    assert app.traductor.ia_activa is False and "GEMINI_API_KEY" in caplog.text


def test_proveedor_mal_escrito_si_falla(repo):
    from app import create_app
    with pytest.raises(RuntimeError, match="no es válido"):
        create_app({**CONFIG_BASE, "PROVEEDOR_IA": "gemin"}, repo=repo)


def test_proveedor_con_clave_se_activa(repo):
    from app import create_app
    app = create_app({**CONFIG_BASE, "PROVEEDOR_IA": "gemini", "GEMINI_API_KEY": "clave-falsa"}, repo=repo)
    assert app.traductor.ia_activa is True


def test_la_clave_no_aparece_en_las_paginas(repo):
    from app import create_app
    app = create_app({**CONFIG_BASE, "PROVEEDOR_IA": "gemini", "GEMINI_API_KEY": "clave-secreta-xyz"}, repo=repo)
    c = app.test_client()
    for ruta in ("/", "/acerca", "/privacidad", "/ejemplos"):
        assert "clave-secreta-xyz" not in c.get(ruta).get_data(as_text=True)


# ---- audio
def test_audio_sirve_solo_archivos_autorizados_dentro_de_la_carpeta(repo, tmp_path):
    from app import create_app
    (tmp_path / "ok.mp3").write_bytes(b"ID3audio")
    (tmp_path.parent / "secreto.txt").write_text("no")
    repo.audios = {1: "ok.mp3", 2: "../secreto.txt", 3: "no_existe.mp3"}
    c = create_app({**CONFIG_BASE, "AUDIO_DIR": str(tmp_path)}, repo=repo).test_client()
    assert c.get("/audio/1").status_code == 200 and c.get("/audio/1").data == b"ID3audio"
    assert c.get("/audio/2").status_code == 404      # intento de salir de la carpeta
    assert c.get("/audio/3").status_code == 404      # archivo faltante
    assert c.get("/audio/99").status_code == 404     # no aprobado / no autorizado (el repo no lo devuelve)


def test_flujo_completo_ruta_motor_gemini_con_http_simulado(repo):
    """Ruta → motor → ProveedorGemini real (HTTP simulado) → estado automática. NO es una llamada real."""
    import json as _json
    from app import create_app
    from test_ia import HttpFalso, Resp
    app = create_app({**CONFIG_BASE, "PROVEEDOR_IA": "gemini", "GEMINI_API_KEY": "clave-falsa"}, repo=repo)
    respuesta = _json.dumps({"traduccion": "propuesta prueba", "confianza": "media", "palabras_sin_respaldo": [], "motivo": ""})
    http = HttpFalso(Resp(200, {"candidates": [{"content": {"parts": [{"text": respuesta}]}}]}))
    app.traductor._ia._http = http
    c = app.test_client()
    import re
    t = re.search(r'data-csrf="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
    d = c.post("/api/traducir", json={"texto": "buenos dias amigo"}, headers={"X-CSRF-Token": t}).get_json()
    assert d["estado"] == "automatica" and d["traduccion"] == "propuesta prueba" and "inteligencia artificial" in d["mensaje"]
    assert http.visto["headers"]["x-goog-api-key"] == "clave-falsa" and "clave-falsa" not in http.visto["url"]
    assert "clave-falsa" not in _json.dumps(d)


def test_error_de_bd_se_registra_con_la_causa_pero_sin_sql_ni_texto(repo, caplog):
    from sqlalchemy.exc import SQLAlchemyError
    from app import create_app

    class _Orig(Exception):
        pass

    def fallar(*a, **k):
        e = SQLAlchemyError("SELECT ... WHERE texto = 'TEXTO PRIVADO'")
        e.orig = _Orig("no such table: uso_ia")
        raise e
    repo.buscar_verificadas = fallar
    app = create_app(dict(CONFIG_BASE), repo=repo)
    c = app.test_client()
    import re
    t = re.search(r'data-csrf="([^"]+)"', c.get("/").get_data(as_text=True)).group(1)
    r = c.post("/api/traducir", json={"texto": "TEXTO PRIVADO"}, headers={"X-CSRF-Token": t})
    assert r.status_code == 503
    assert "no such table: uso_ia" in caplog.text and "PRIVADO" not in caplog.text and "SELECT" not in caplog.text
