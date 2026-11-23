"""Acceso a la base de datos (SQLAlchemy). TODAS las consultas de la aplicación viven aquí.

Las demás partes del programa (rutas, motor de traducción) no usan el ORM directamente:
llaman a estas funciones y reciben diccionarios o `SimpleNamespace` sencillos.
Todas las consultas están parametrizadas (no se arma SQL con texto del usuario).

Regla de visibilidad (función `_visibles`): una traducción solo se muestra al público si
está VERIFICADA, su variante está activa y, si viene de una fuente publicada, esa fuente
tiene permiso de uso (`autorizado` o `no_aplica`).
"""
import logging
from datetime import datetime, timezone
from types import SimpleNamespace

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import aliased

from extensions import db
from models import (Audio, Categoria, Fuente, Hablante, Perfil, TokenRecuperacion,
                    Traduccion, UsoIA, Usuario, Variante)

from .texto import normalizar_es
from .tipos import CorreoDuplicado, Hallada  # noqa: F401

MAX_CANDIDATOS_CONTEXTO = 40


def _ahora():
    return datetime.now(timezone.utc)


def _con_zona(fecha):
    """MySQL devuelve fechas sin zona; en la base siempre se guarda UTC."""
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Cuentas
# ---------------------------------------------------------------------------
def _usuario(u):
    if u is None:
        return None
    p = u.perfil
    perfil = {
        "pronombres": p.pronombres if p else "", "biografia": p.biografia if p else "",
        "instagram": p.instagram if p else "", "facebook": p.facebook if p else "",
        "tiktok": p.tiktok if p else "", "youtube": p.youtube if p else "",
        "sitio_web": p.sitio_web if p else "",
    }
    return SimpleNamespace(id=u.id, nombre=u.nombre, correo=u.correo, rol=u.rol, activo=u.activo,
                           contrasena_hash=u.contrasena_hash, creado_en=u.creado_en, perfil=perfil)


def usuario_por_correo(correo):
    u = db.session.execute(select(Usuario).where(Usuario.correo == correo)).scalar_one_or_none()
    return _usuario(u)


def usuario_por_id(usuario_id):
    return _usuario(db.session.get(Usuario, usuario_id))


def crear_usuario(nombre, correo, contrasena_hash):
    """Crea la cuenta (rol «usuario») y su perfil vacío. Lanza CorreoDuplicado si ya existe."""
    usuario = Usuario(nombre=nombre, correo=correo, contrasena_hash=contrasena_hash, rol="usuario")
    usuario.perfil = Perfil()
    db.session.add(usuario)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise CorreoDuplicado(correo)
    return _usuario(usuario)


def actualizar_cuenta(usuario_id, datos):
    """Guarda nombre y perfil. `datos` viene ya validado (ver servicios/validacion.py)."""
    usuario = db.session.get(Usuario, usuario_id)
    usuario.nombre = datos["nombre"]
    if usuario.perfil is None:
        usuario.perfil = Perfil()
    for campo in ("pronombres", "biografia", "instagram", "facebook", "tiktok", "youtube", "sitio_web"):
        setattr(usuario.perfil, campo, datos.get(campo, ""))
    db.session.commit()


def registrar_acceso(usuario_id):
    db.session.execute(update(Usuario).where(Usuario.id == usuario_id).values(ultimo_acceso=_ahora()))
    db.session.commit()


def cambiar_contrasena(usuario_id, contrasena_hash):
    """Cambia la contraseña e invalida los enlaces de recuperación pendientes."""
    db.session.execute(update(Usuario).where(Usuario.id == usuario_id).values(contrasena_hash=contrasena_hash))
    db.session.execute(update(TokenRecuperacion)
                       .where(TokenRecuperacion.usuario_id == usuario_id, TokenRecuperacion.usado.is_(False))
                       .values(usado=True))
    db.session.commit()


def asignar_rol(correo, rol):
    """Para el comando de servidor `asignar-rol`. Devuelve True si existía la cuenta."""
    resultado = db.session.execute(update(Usuario).where(Usuario.correo == correo).values(rol=rol))
    db.session.commit()
    return resultado.rowcount == 1


# ---------------------------------------------------------------------------
# Recuperación de contraseña (solo se guarda el hash del token)
# ---------------------------------------------------------------------------
def guardar_token(usuario_id, token_hash, expira):
    db.session.add(TokenRecuperacion(usuario_id=usuario_id, token_hash=token_hash, expira=expira))
    db.session.commit()


def tokens_recientes(usuario_id, desde):
    consulta = select(func.count(TokenRecuperacion.id)).where(
        TokenRecuperacion.usuario_id == usuario_id, TokenRecuperacion.creado_en >= desde)
    return db.session.execute(consulta).scalar_one()


def _token(token_hash):
    return db.session.execute(
        select(TokenRecuperacion).where(TokenRecuperacion.token_hash == token_hash)).scalar_one_or_none()


def token_vigente(token_hash):
    fila = _token(token_hash)
    return bool(fila and not fila.usado and _con_zona(fila.expira) > _ahora())


def consumir_token(token_hash):
    """Marca el token como usado y devuelve el id del usuario (o None si no sirve).

    La actualización lleva `usado = false` en el WHERE: si dos personas lo usan a la vez,
    solo una obtiene `rowcount == 1`.
    """
    fila = _token(token_hash)
    if not fila or fila.usado or _con_zona(fila.expira) <= _ahora():
        return None
    resultado = db.session.execute(
        update(TokenRecuperacion)
        .where(TokenRecuperacion.id == fila.id, TokenRecuperacion.usado.is_(False))
        .values(usado=True))
    db.session.commit()
    return fila.usuario_id if resultado.rowcount == 1 else None


# ---------------------------------------------------------------------------
# Contenido visible al público
# ---------------------------------------------------------------------------
def _visibles(codigo_variante):
    """Condiciones que debe cumplir una traducción para mostrarse al público."""
    return [
        Variante.codigo == codigo_variante,
        Variante.activa.is_(True),
        Traduccion.estado == "verificada",
        or_(Traduccion.fuente_id.is_(None), Fuente.permiso_estado.in_(("autorizado", "no_aplica"))),
    ]


def _consulta_visibles(*columnas):
    return (select(*columnas).select_from(Traduccion)
            .join(Variante, Variante.id == Traduccion.variante_id)
            .outerjoin(Fuente, Fuente.id == Traduccion.fuente_id)
            .outerjoin(Categoria, Categoria.id == Traduccion.categoria_id))


def _procedencia(t):
    """Texto de procedencia. El nombre del hablante solo aparece si dio su consentimiento."""
    partes = []
    if t.fuente is not None:
        detalle = ", ".join(str(x) for x in (t.fuente.autores, t.fuente.anio) if x)
        partes.append(f"Fuente: {t.fuente.titulo}" + (f" ({detalle})" if detalle else ""))
    if t.verificada_por is not None:
        h = t.verificada_por
        nombre = h.nombre_publico if h.consentimiento_creditos else "una persona hablante de la variante"
        partes.append(f"Revisada por {nombre}")
    return " · ".join(partes)


def _entradas(traducciones):
    """Convierte filas de Traduccion en diccionarios, con audio y ejemplos verificados."""
    if not traducciones:
        return []
    ids = [t.id for t in traducciones]
    audios = dict(db.session.execute(
        select(Audio.traduccion_id, func.min(Audio.id))
        .where(Audio.traduccion_id.in_(ids), Audio.estado == "aprobado", Audio.autorizado.is_(True))
        .group_by(Audio.traduccion_id)).all())
    ejemplos = {}
    ej = aliased(Traduccion)
    filas = db.session.execute(
        select(ej.ejemplo_de_id, ej.texto_es, ej.texto_mixteco)
        .outerjoin(Fuente, Fuente.id == ej.fuente_id)
        .where(ej.ejemplo_de_id.in_(ids), ej.estado == "verificada",
               or_(ej.fuente_id.is_(None), Fuente.permiso_estado.in_(("autorizado", "no_aplica"))))
        .order_by(ej.id)).all()
    for padre, es, mixteco in filas:
        ejemplos.setdefault(padre, []).append({"es": es, "mixteco": mixteco})
    return [{
        "id": t.id, "es": t.texto_es, "mixteco": t.texto_mixteco, "tipo": t.tipo,
        "categoria": t.categoria.nombre if t.categoria else None,
        "procedencia": _procedencia(t), "audio_id": audios.get(t.id),
        "ejemplos": ejemplos.get(t.id, []),
    } for t in traducciones]


def _filas_visibles(codigo_variante, *condiciones, limite=None, desplazamiento=0):
    consulta = (_consulta_visibles(Traduccion)
                .where(*_visibles(codigo_variante), *condiciones)
                .order_by(Traduccion.texto_es_norm, Traduccion.id))
    if limite:
        consulta = consulta.limit(limite).offset(desplazamiento)
    return db.session.execute(consulta).scalars().unique().all()


def buscar_verificadas(texto_norm, codigo_variante):
    """Traducciones verificadas cuyo texto en español coincide COMPLETO con `texto_norm`."""
    filas = _filas_visibles(codigo_variante, Traduccion.texto_es_norm == texto_norm,
                            Traduccion.ejemplo_de_id.is_(None), limite=5)
    return [Hallada(texto=e["mixteco"], categoria=e["categoria"], procedencia=e["procedencia"],
                    audio_id=e["audio_id"], ejemplos=e["ejemplos"], tipo=e["tipo"])
            for e in _entradas(filas)]


def vocabulario(codigo_variante, categoria=None, tipo=None, busqueda=None, pagina=1, por_pagina=30):
    """Lista paginada para «Ejemplos y vocabulario». Devuelve (entradas, total)."""
    condiciones = [Traduccion.ejemplo_de_id.is_(None)]
    if categoria:
        condiciones.append(Categoria.clave == categoria)
    if tipo:
        condiciones.append(Traduccion.tipo == tipo)
    if busqueda:
        condiciones.append(Traduccion.texto_es_norm.contains(normalizar_es(busqueda), autoescape=True))
    total = db.session.execute(
        _consulta_visibles(func.count(Traduccion.id)).where(*_visibles(codigo_variante), *condiciones)
    ).scalar_one()
    filas = _filas_visibles(codigo_variante, *condiciones, limite=por_pagina,
                            desplazamiento=(max(pagina, 1) - 1) * por_pagina)
    return _entradas(filas), total


def categorias_con_conteo(codigo_variante):
    """[(clave, nombre, cantidad)] de las categorías que tienen contenido visible."""
    consulta = (_consulta_visibles(Categoria.clave, Categoria.nombre, func.count(Traduccion.id))
                .where(*_visibles(codigo_variante), Traduccion.ejemplo_de_id.is_(None),
                       Categoria.id.is_not(None))
                .group_by(Categoria.clave, Categoria.nombre).order_by(Categoria.nombre))
    return [tuple(f) for f in db.session.execute(consulta).all()]


def contar_verificadas(codigo_variante):
    return db.session.execute(
        _consulta_visibles(func.count(Traduccion.id)).where(*_visibles(codigo_variante))).scalar_one()


def buscar_contexto(texto_norm, codigo_variante, limite=15):
    """Entradas verificadas relacionadas con el texto, para dárselas a la IA como contexto.

    Se buscan las palabras sueltas y las combinaciones de 2 y 3 palabras seguidas.
    Las más largas (más específicas) van primero.
    """
    palabras = texto_norm.split()
    candidatos = {p for p in palabras if len(p) >= 2}
    for n in (2, 3):
        candidatos.update(" ".join(palabras[i:i + n]) for i in range(len(palabras) - n + 1))
    candidatos = sorted(candidatos, key=len, reverse=True)[:MAX_CANDIDATOS_CONTEXTO]
    if not candidatos:
        return []
    filas = _filas_visibles(codigo_variante, Traduccion.texto_es_norm.in_(candidatos),
                            Traduccion.ejemplo_de_id.is_(None))
    filas.sort(key=lambda t: len(t.texto_es_norm), reverse=True)
    return [{"es": t.texto_es, "mixteco": t.texto_mixteco, "tipo": t.tipo} for t in filas[:limite]]


# ---------------------------------------------------------------------------
# Aportes de usuarios (quedan PENDIENTES: nunca se muestran como verificados)
# ---------------------------------------------------------------------------
def crear_aporte(codigo_variante, espanol, mixteco, tipo, usuario_id):
    """Guarda un aporte pendiente. Devuelve True, o False si ya estaba registrado."""
    variante = db.session.execute(select(Variante).where(Variante.codigo == codigo_variante)).scalar_one_or_none()
    if variante is None:
        raise ValueError(f"La variante {codigo_variante} no está en la base de datos (ejecuta init-db).")
    norm = normalizar_es(espanol)
    repetido = db.session.execute(
        select(Traduccion.id).where(Traduccion.variante_id == variante.id, Traduccion.texto_es_norm == norm,
                                    Traduccion.texto_mixteco == mixteco, Traduccion.estado != "rechazada")
        .limit(1)).first()
    if repetido:
        return False
    db.session.add(Traduccion(variante_id=variante.id, tipo=tipo, texto_es=espanol, texto_es_norm=norm,
                              texto_mixteco=mixteco, estado="pendiente", origen="usuario",
                              aportada_por_id=usuario_id))
    db.session.commit()
    return True


def mis_aportes(usuario_id, limite=20):
    filas = db.session.execute(
        select(Traduccion.texto_es, Traduccion.texto_mixteco, Traduccion.estado, Traduccion.creada_en)
        .where(Traduccion.aportada_por_id == usuario_id)
        .order_by(Traduccion.id.desc()).limit(limite)).all()
    return [{"es": f[0], "mixteco": f[1], "estado": f[2], "fecha": f[3]} for f in filas]


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------
def audio_ruta(audio_id):
    """Ruta relativa del archivo si el audio está aprobado, autorizado y su traducción es visible."""
    consulta = (select(Audio.ruta_archivo)
                .join(Traduccion, Traduccion.id == Audio.traduccion_id)
                .join(Variante, Variante.id == Traduccion.variante_id)
                .outerjoin(Fuente, Fuente.id == Traduccion.fuente_id)
                .where(Audio.id == audio_id, Audio.estado == "aprobado", Audio.autorizado.is_(True),
                       Traduccion.estado == "verificada", Variante.activa.is_(True),
                       or_(Traduccion.fuente_id.is_(None), Fuente.permiso_estado.in_(("autorizado", "no_aplica")))))
    return db.session.execute(consulta).scalar_one_or_none()


# ---------------------------------------------------------------------------
# Tope diario de llamadas a la IA (global, aunque haya varias instancias)
# ---------------------------------------------------------------------------
def reservar_llamada_ia(limite):
    """Reserva una llamada de hoy. False si se alcanzó el tope o si la base falla (falla cerrada)."""
    if limite <= 0:
        return False
    hoy = _ahora().date()
    try:
        for _ in range(2):
            resultado = db.session.execute(
                update(UsoIA).where(UsoIA.fecha == hoy, UsoIA.llamadas < limite)
                .values(llamadas=UsoIA.llamadas + 1))
            if resultado.rowcount == 1:
                db.session.commit()
                return True
            if db.session.get(UsoIA, hoy) is not None:     # el renglón existe: tope alcanzado
                db.session.commit()
                return False
            db.session.add(UsoIA(fecha=hoy, llamadas=1))
            try:
                db.session.commit()
                return True
            except IntegrityError:                          # otra instancia lo creó al mismo tiempo
                db.session.rollback()
        return False
    except SQLAlchemyError as e:
        db.session.rollback()
        causa = getattr(e, "orig", None)
        logging.getLogger("raices.repositorio").error(
            "No se pudo reservar la llamada de IA (%s: %s)", type(causa or e).__name__, str(causa or "")[:200])
        return False
