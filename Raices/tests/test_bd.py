"""Pruebas de las consultas REALES (servicios/repositorio.py + models.py) con SQLAlchemy y SQLite en memoria.

Se omiten solas si SQLAlchemy / Flask-SQLAlchemy no están instalados (pip install -r requirements.txt).
SQLite no es MySQL: estas pruebas validan la lógica de las consultas y las restricciones CHECK/UNIQUE,
pero no el cotejo (collation) ni los tipos propios de MySQL; para eso, ejecutar la app contra MySQL.
"""
from datetime import datetime, timedelta, timezone

import pytest

from conftest import DEPENDENCIAS_REALES

pytestmark = pytest.mark.skipif(not DEPENDENCIAS_REALES, reason="SQLAlchemy no está instalado")


@pytest.fixture
def bd():
    from app import create_app
    from extensions import db
    app = create_app({"TESTING": True, "SECRET_KEY": "x", "SQLALCHEMY_DATABASE_URI": "sqlite://",
                      "SQLALCHEMY_ENGINE_OPTIONS": {}, "PROVEEDOR_IA": "ninguno"})
    with app.app_context():
        db.create_all()
        yield db
        db.session.remove()
        db.drop_all()


def _datos(db):
    from models import Categoria, Fuente, Hablante, Traduccion, Variante
    v = Variante(codigo="mxb", nombre="Mixteco de prueba", activa=True)
    db.session.add(v)
    db.session.flush()
    h = Hablante(nombre_publico="Hablante de prueba", variante_id=v.id, consentimiento_creditos=False)
    ok = Fuente(titulo="Fuente autorizada", tipo="diccionario", permiso_estado="autorizado")
    no = Fuente(titulo="Fuente sin permiso", tipo="diccionario", permiso_estado="sin_solicitar")
    c = Categoria(clave="prueba", nombre="Prueba")
    db.session.add_all([h, ok, no, c])
    db.session.flush()
    ahora = datetime.now(timezone.utc)

    def t(es, estado="verificada", **kw):
        fila = Traduccion(variante_id=v.id, tipo="palabra", texto_es=es, texto_es_norm=es.lower(), texto_mixteco=f"mx-{es}",
                          estado=estado, origen=kw.pop("origen", "hablante"), categoria_id=c.id, **kw)
        db.session.add(fila)
        db.session.flush()
        return fila

    return dict(v=v, h=h, ok=ok, no=no, ahora=ahora, t=t)


def test_visibilidad_solo_verificadas_con_permiso(bd):
    from servicios import repositorio as r
    d = _datos(bd)
    d["t"]("revisada", verificada_por_id=d["h"].id, verificada_en=d["ahora"])
    d["t"]("fuente_ok", fuente_id=d["ok"].id, origen="fuente_publicada")
    d["t"]("fuente_sin_permiso", fuente_id=d["no"].id, origen="fuente_publicada")
    d["t"]("pendiente", estado="pendiente", origen="usuario")
    bd.session.commit()
    assert [h.texto for h in r.buscar_verificadas("revisada", "mxb")] == ["mx-revisada"]
    assert r.buscar_verificadas("fuente_sin_permiso", "mxb") == []
    assert r.buscar_verificadas("pendiente", "mxb") == []
    assert r.contar_verificadas("mxb") == 2
    assert r.buscar_verificadas("revisada", "otra") == []


def test_nombre_del_hablante_solo_con_consentimiento(bd):
    from servicios import repositorio as r
    d = _datos(bd)
    d["t"]("revisada", verificada_por_id=d["h"].id, verificada_en=d["ahora"])
    bd.session.commit()
    assert "Hablante de prueba" not in r.buscar_verificadas("revisada", "mxb")[0].procedencia
    d["h"].consentimiento_creditos = True
    bd.session.commit()
    assert "Hablante de prueba" in r.buscar_verificadas("revisada", "mxb")[0].procedencia


def test_restricciones_verificada_necesita_respaldo_e_ia_necesita_persona(bd):
    from sqlalchemy.exc import IntegrityError
    d = _datos(bd)
    with pytest.raises(IntegrityError):
        d["t"]("sin_respaldo")
        bd.session.commit()
    bd.session.rollback()


def test_vocabulario_filtros_y_paginacion(bd):
    from servicios import repositorio as r
    d = _datos(bd)
    for i in range(5):
        d["t"](f"palabra{i}", fuente_id=d["ok"].id, origen="fuente_publicada")
    bd.session.commit()
    entradas, total = r.vocabulario("mxb", por_pagina=2, pagina=3)
    assert total == 5 and len(entradas) == 1
    assert r.vocabulario("mxb", busqueda="palabra3")[1] == 1
    assert r.vocabulario("mxb", categoria="otra")[1] == 0
    assert r.categorias_con_conteo("mxb") == [("prueba", "Prueba", 5)]


def test_contexto_para_la_ia_solo_verificado(bd):
    from servicios import repositorio as r
    d = _datos(bd)
    d["t"]("hola", fuente_id=d["ok"].id, origen="fuente_publicada")
    d["t"]("amigo", estado="pendiente", origen="usuario")
    bd.session.commit()
    ctx = r.buscar_contexto("hola amigo", "mxb")
    assert [c["es"] for c in ctx] == ["hola"]


def test_usuarios_duplicados_y_tokens(bd):
    from servicios import repositorio as r
    from servicios.tipos import CorreoDuplicado
    u = r.crear_usuario("Ana", "ana@example.com", "hash")
    assert u.rol == "usuario" and r.usuario_por_correo("ana@example.com").id == u.id
    with pytest.raises(CorreoDuplicado):
        r.crear_usuario("Otra", "ana@example.com", "hash2")
    ahora = datetime.now(timezone.utc)
    r.guardar_token(u.id, "a" * 64, ahora + timedelta(minutes=30))
    r.guardar_token(u.id, "b" * 64, ahora - timedelta(minutes=1))
    assert r.token_vigente("a" * 64) and not r.token_vigente("b" * 64)
    assert r.consumir_token("a" * 64) == u.id and r.consumir_token("a" * 64) is None
    assert r.consumir_token("b" * 64) is None and r.tokens_recientes(u.id, ahora - timedelta(hours=1)) == 2


def test_cambiar_contrasena_invalida_tokens(bd):
    from servicios import repositorio as r
    u = r.crear_usuario("Ana", "ana@example.com", "hash")
    r.guardar_token(u.id, "c" * 64, datetime.now(timezone.utc) + timedelta(minutes=30))
    r.cambiar_contrasena(u.id, "nuevo")
    assert not r.token_vigente("c" * 64) and r.usuario_por_id(u.id).contrasena_hash == "nuevo"


def test_asignar_rol(bd):
    from servicios import repositorio as r
    r.crear_usuario("Ana", "ana@example.com", "h")
    assert r.asignar_rol("ana@example.com", "hablante") and not r.asignar_rol("x@example.com", "hablante")
    assert r.usuario_por_correo("ana@example.com").rol == "hablante"


def test_aporte_queda_pendiente_y_no_duplica(bd):
    from servicios import repositorio as r
    _datos(bd)
    bd.session.commit()
    u = r.crear_usuario("Ana", "ana@example.com", "h")
    assert r.crear_aporte("mxb", "Agua", "dato", "palabra", u.id) is True
    assert r.crear_aporte("mxb", "agua", "dato", "palabra", u.id) is False
    assert r.mis_aportes(u.id)[0]["estado"] == "pendiente" and r.contar_verificadas("mxb") == 0


def test_audio_solo_aprobado_autorizado_y_visible(bd):
    from models import Audio
    from servicios import repositorio as r
    d = _datos(bd)
    t = d["t"]("hola", verificada_por_id=d["h"].id, verificada_en=d["ahora"])
    a1 = Audio(traduccion_id=t.id, ruta_archivo="a.mp3", origen="grabacion", hablante_id=d["h"].id, autorizado=True, estado="aprobado")
    a2 = Audio(traduccion_id=t.id, ruta_archivo="b.mp3", origen="grabacion", hablante_id=d["h"].id, autorizado=True, estado="pendiente")
    bd.session.add_all([a1, a2])
    bd.session.commit()
    assert r.audio_ruta(a1.id) == "a.mp3" and r.audio_ruta(a2.id) is None
    assert r.buscar_verificadas("hola", "mxb")[0].audio_id == a1.id


def test_audio_de_grabacion_sin_autorizacion_no_se_puede_guardar(bd):
    from sqlalchemy.exc import IntegrityError
    from models import Audio
    d = _datos(bd)
    t = d["t"]("hola", verificada_por_id=d["h"].id, verificada_en=d["ahora"])
    bd.session.add(Audio(traduccion_id=t.id, ruta_archivo="a.mp3", origen="grabacion", hablante_id=d["h"].id, autorizado=False))
    with pytest.raises(IntegrityError):
        bd.session.commit()


def test_tope_diario_de_ia(bd):
    from servicios import repositorio as r
    assert [r.reservar_llamada_ia(2) for _ in range(3)] == [True, True, False]
    assert r.reservar_llamada_ia(0) is False
