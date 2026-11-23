import re

import pytest

from conftest import CONFIG_BASE, token

CLAVE = "Segura123"


def registrar(c, correo="ana@example.com", nombre="Ana López", clave=CLAVE, confirmar=None):
    return c.post("/registro", data={"csrf": token(c, "/registro"), "nombre": nombre, "correo": correo,
                                     "contrasena": clave, "confirmar": clave if confirmar is None else confirmar})


def entrar(c, correo="ana@example.com", clave=CLAVE, **extra):
    return c.post("/login", data={"csrf": token(c, "/login"), "correo": correo, "contrasena": clave, **extra})


def salir(c):
    return c.post("/logout", data={"csrf": token(c, "/cuenta")})


def test_registro_crea_cuenta_con_hash_y_abre_sesion(cliente, repo):
    r = registrar(cliente)
    assert r.status_code == 302 and r.headers["Location"].endswith("/cuenta")
    u = repo.usuario_por_correo("ana@example.com")
    assert u.rol == "usuario" and u.contrasena_hash != CLAVE and u.contrasena_hash.startswith(("scrypt:", "pbkdf2:"))
    assert "Ana López" in cliente.get("/cuenta").get_data(as_text=True)


def test_registro_sin_csrf_es_rechazado(cliente, repo):
    r = cliente.post("/registro", data={"nombre": "A", "correo": "a@b.co", "contrasena": CLAVE, "confirmar": CLAVE})
    assert r.status_code == 302 and not repo.usuarios


@pytest.mark.parametrize("nombre,correo,clave,confirmar,texto", [
    ("", "a@b.co", CLAVE, CLAVE, "Escribe tu nombre"),
    ("Ana", "no-es-correo", CLAVE, CLAVE, "formato válido"),
    ("Ana", "a@b.co", "corta1A", "corta1A", "al menos 8"),
    ("Ana", "a@b.co", "sinmayuscula1", "sinmayuscula1", "mayúscula"),
    ("Ana", "a@b.co", "SinNumeroAbc", "SinNumeroAbc", "número"),
    ("Ana", "a@b.co", CLAVE, "Otra1234A", "no coinciden"),
])
def test_registro_valida(cliente, repo, nombre, correo, clave, confirmar, texto):
    r = registrar(cliente, correo, nombre, clave, confirmar)
    assert r.status_code == 400 and texto in r.get_data(as_text=True) and not repo.usuarios


def test_registro_correo_duplicado_ignora_mayusculas(cliente, repo):
    registrar(cliente)
    salir(cliente)
    r = registrar(cliente, correo="ANA@Example.com")
    assert r.status_code == 409 and "Ya existe una cuenta" in r.get_data(as_text=True) and len(repo.usuarios) == 1


def test_login_correcto_incorrecto_y_mensaje_generico(cliente):
    registrar(cliente)
    salir(cliente)
    mal = entrar(cliente, clave="Equivocada1")
    inexistente = entrar(cliente, correo="nadie@example.com")
    assert mal.status_code == inexistente.status_code == 401
    assert "Correo o contraseña incorrectos" in mal.get_data(as_text=True)
    assert "Correo o contraseña incorrectos" in inexistente.get_data(as_text=True)   # no revela si existe
    assert entrar(cliente).status_code == 302


def test_bloqueo_tras_intentos_fallidos_incluso_con_la_clave_correcta(cliente):
    registrar(cliente)
    salir(cliente)
    for _ in range(CONFIG_BASE.get("MAX_INTENTOS_LOGIN", 5)):
        assert entrar(cliente, clave="Equivocada1").status_code == 401
    r = entrar(cliente)
    assert r.status_code == 429 and "Demasiados intentos" in r.get_data(as_text=True)


def test_rutas_protegidas_redirigen_al_login(cliente):
    for ruta in ("/cuenta", "/aportar"):
        r = cliente.get(ruta)
        assert r.status_code == 302 and "/login" in r.headers["Location"]
    assert cliente.post("/cuenta", data={}).status_code == 302


def test_logout_cierra_sesion_y_solo_por_post(cliente):
    registrar(cliente)
    assert cliente.get("/logout").status_code == 405
    salir(cliente)
    assert cliente.get("/cuenta").status_code == 302


def test_sesion_de_cuenta_desactivada_se_invalida(cliente, repo):
    registrar(cliente)
    repo.usuarios[1]["activo"] = False
    assert cliente.get("/cuenta").status_code == 302


def test_recordar_sesion_hace_la_cookie_persistente(cliente):
    registrar(cliente)
    salir(cliente)
    r = entrar(cliente, recordar="1")
    assert "Expires=" in r.headers["Set-Cookie"] or "Max-Age" in r.headers["Set-Cookie"]
    salir(cliente)
    assert "Expires=" not in entrar(cliente).headers["Set-Cookie"]


def test_editar_cuenta_valida_y_guarda(cliente, repo):
    registrar(cliente)
    t = token(cliente, "/cuenta")
    ok = cliente.post("/cuenta", data={"csrf": t, "nombre": "Ana María", "pronombres": "ella", "biografia": "Hola",
                                       "instagram": "https://instagram.com/ana"})
    assert ok.status_code == 302 and repo.usuarios[1]["nombre"] == "Ana María" and repo.usuarios[1]["perfil"]["pronombres"] == "ella"
    mal = cliente.post("/cuenta", data={"csrf": t, "nombre": "Ana", "instagram": "https://malo.com/x"})
    assert mal.status_code == 400 and "Instagram no es válido" in mal.get_data(as_text=True)
    vacio = cliente.post("/cuenta", data={"csrf": t, "nombre": ""})
    assert vacio.status_code == 400


def test_cambiar_contrasena(cliente):
    registrar(cliente)
    t = token(cliente, "/cuenta")
    mal = cliente.post("/cuenta/contrasena", data={"csrf": t, "actual": "Equivocada1", "nueva": "Nueva1234", "confirmar": "Nueva1234"})
    assert mal.status_code == 400 and "actual no es correcta" in mal.get_data(as_text=True)
    ok = cliente.post("/cuenta/contrasena", data={"csrf": t, "actual": CLAVE, "nueva": "Nueva1234", "confirmar": "Nueva1234"})
    assert ok.status_code == 302
    salir(cliente)
    assert entrar(cliente, clave=CLAVE).status_code == 401 and entrar(cliente, clave="Nueva1234").status_code == 302


# ---- aportes
def test_aporte_queda_pendiente_nunca_verificado(cliente, repo):
    registrar(cliente)
    r = cliente.post("/aportar", data={"csrf": token(cliente, "/aportar"), "espanol": "Agua", "mixteco": "dato de prueba"})
    assert r.status_code == 302
    assert repo.aportes[0]["estado"] == "pendiente" and repo.aportes[0]["tipo"] == "palabra"
    assert repo.contar_verificadas("mxb") == 0 and "Pendiente de revisión" in cliente.get("/cuenta").get_data(as_text=True)


def test_aporte_valida_y_limita(repo):
    from app import create_app
    c = create_app({**CONFIG_BASE, "MAX_APORTES_POR_HORA": 2}, repo=repo).test_client()
    registrar(c)
    t = token(c, "/aportar")
    assert c.post("/aportar", data={"csrf": t, "espanol": "", "mixteco": "x"}).status_code == 400
    assert c.post("/aportar", data={"csrf": t, "espanol": "<b>", "mixteco": "x"}).status_code == 400
    codigos = [c.post("/aportar", data={"csrf": t, "espanol": f"p{i}", "mixteco": "dato"}).status_code for i in range(3)]
    assert codigos == [302, 302, 400]


# ---- recuperación
def _enlace(caplog):
    return re.search(r"http://localhost(/recuperar/[\w-]+)", caplog.text).group(1)


def test_recuperacion_completa_y_token_de_un_solo_uso(cliente, repo, caplog):
    registrar(cliente)
    salir(cliente)
    r = cliente.post("/recuperar", data={"csrf": token(cliente, "/recuperar"), "correo": "ana@example.com"})
    assert r.status_code == 200 and "Revisa tu correo" in r.get_data(as_text=True)
    enlace = _enlace(caplog)
    assert all(len(h) == 64 for h in repo.tokens) and enlace.split("/")[-1] not in repo.tokens   # solo se guarda el hash
    t = token(cliente, enlace)
    ok = cliente.post(enlace, data={"csrf": t, "nueva": "Nueva1234", "confirmar": "Nueva1234"})
    assert ok.status_code == 302 and "/login" in ok.headers["Location"]
    assert entrar(cliente, clave="Nueva1234").status_code == 302
    salir(cliente)
    assert cliente.get(enlace).status_code == 400          # ya usado


def test_recuperacion_no_revela_si_el_correo_existe(cliente, caplog):
    t = token(cliente, "/recuperar")
    a = cliente.post("/recuperar", data={"csrf": t, "correo": "nadie@example.com"})
    registrar(cliente)
    salir(cliente)
    b = cliente.post("/recuperar", data={"csrf": token(cliente, "/recuperar"), "correo": "ana@example.com"})
    assert a.status_code == b.status_code and a.get_data(as_text=True).count("Revisa tu correo") == 1 == b.get_data(as_text=True).count("Revisa tu correo")


def test_token_invalido_o_vencido(cliente, repo, caplog):
    assert cliente.get("/recuperar/token-falso").status_code == 400
    registrar(cliente)
    salir(cliente)
    cliente.post("/recuperar", data={"csrf": token(cliente, "/recuperar"), "correo": "ana@example.com"})
    enlace = _enlace(caplog)
    from datetime import datetime, timedelta, timezone
    for t in repo.tokens.values():
        t["expira"] = datetime.now(timezone.utc) - timedelta(minutes=1)
    assert cliente.get(enlace).status_code == 400


def test_limite_de_solicitudes_de_recuperacion_por_usuario(cliente, repo, caplog):
    registrar(cliente)
    salir(cliente)
    for _ in range(8):
        cliente.post("/recuperar", data={"csrf": token(cliente, "/recuperar"), "correo": "ana@example.com"})
    assert len(repo.tokens) == CONFIG_BASE.get("MAX_SOLICITUDES_RECUPERACION", 5)


def test_nueva_contrasena_debe_cumplir_reglas(cliente, caplog):
    registrar(cliente)
    salir(cliente)
    cliente.post("/recuperar", data={"csrf": token(cliente, "/recuperar"), "correo": "ana@example.com"})
    enlace = _enlace(caplog)
    r = cliente.post(enlace, data={"csrf": token(cliente, enlace), "nueva": "corta", "confirmar": "corta"})
    assert r.status_code == 400
