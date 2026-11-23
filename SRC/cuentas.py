"""Cuentas de usuario: registro, inicio/cierre de sesión, perfil, contraseña y recuperación.

Sesión: la cookie firmada guarda solo el id del usuario. Al iniciar sesión se vacía la sesión
anterior (evita fijación de sesión). La contraseña se guarda con hash (scrypt, de werkzeug).
Todos los formularios llevan el campo oculto «csrf» (se verifica en app.py para todo POST).
"""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import (Blueprint, current_app, flash, g, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from seguridad import token_csrf
from servicios import correo, validacion
from servicios.tipos import CorreoDuplicado

bp = Blueprint("cuentas", __name__)
log = logging.getLogger(__name__)

# Hash de relleno: al iniciar sesión con un correo inexistente también se calcula un hash,
# para que el tiempo de respuesta no revele si la cuenta existe.
_HASH_RELLENO = generate_password_hash("relleno-no-es-una-contrasena")
MENSAJE_LOGIN = "Correo o contraseña incorrectos."
MENSAJE_BLOQUEO = "Demasiados intentos fallidos. Espera unos minutos antes de volver a intentar."


def repo():
    return current_app.repo


def login_required(vista):
    @wraps(vista)
    def envoltura(*args, **kwargs):
        if g.get("usuario") is None:
            flash("Inicia sesión para continuar.", "info")
            return redirect(url_for("cuentas.login"))
        return vista(*args, **kwargs)
    return envoltura


def cargar_usuario():
    """Se ejecuta antes de cada petición (registrado en app.py)."""
    g.usuario = None
    uid = session.get("uid")
    if uid is None:
        return
    usuario = repo().usuario_por_id(uid)
    if usuario is None or not usuario.activo:
        session.clear()
        return
    g.usuario = usuario


def _iniciar_sesion(usuario, recordar):
    session.clear()
    session["uid"] = usuario.id
    session.permanent = bool(recordar)
    repo().registrar_acceso(usuario.id)


def _ip():
    return request.remote_addr or "desconocida"


def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


# ---------------------------------------------------------------------------
@bp.route("/registro", methods=["GET", "POST"])
def registro():
    if g.usuario:
        return redirect(url_for("cuentas.cuenta"))
    if request.method == "GET":
        return render_template("registro.html", form={}, errores=[])

    nombre = validacion.limpiar_nombre(request.form.get("nombre"))
    correo_ = (request.form.get("correo") or "").strip().lower()
    contrasena = request.form.get("contrasena") or ""
    form = {"nombre": nombre, "correo": correo_}
    errores = validacion.validar_registro(nombre, correo_, contrasena)
    if contrasena != (request.form.get("confirmar") or ""):
        errores.append("Las contraseñas no coinciden.")
    if not current_app.limitador_cuentas.permitir(_ip()):
        errores = ["Demasiados intentos desde esta conexión. Espera un momento."]
    if errores:
        return render_template("registro.html", form=form, errores=errores), 400

    try:
        usuario = repo().crear_usuario(nombre, correo_, generate_password_hash(contrasena))
    except CorreoDuplicado:
        return render_template("registro.html", form=form,
                               errores=["Ya existe una cuenta con ese correo. Inicia sesión o recupera tu contraseña."]), 409
    _iniciar_sesion(usuario, recordar=False)
    flash("Tu cuenta fue creada. ¡Bienvenida o bienvenido a Raíces!", "exito")
    return redirect(url_for("cuentas.cuenta"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.usuario:
        return redirect(url_for("cuentas.cuenta"))
    if request.method == "GET":
        return render_template("login.html", form={}, errores=[])

    correo_ = (request.form.get("correo") or "").strip().lower()
    contrasena = request.form.get("contrasena") or ""
    clave = f"{_ip()}|{correo_}"
    limitador = current_app.limitador_login
    if limitador.bloqueado(clave):
        return render_template("login.html", form={"correo": correo_}, errores=[MENSAJE_BLOQUEO]), 429

    usuario = repo().usuario_por_correo(correo_) if len(correo_) <= validacion.LIMITE_CORREO else None
    valido = check_password_hash(usuario.contrasena_hash if usuario else _HASH_RELLENO, contrasena[:validacion.LIMITE_PASSWORD])
    if not (usuario and usuario.activo and valido):
        limitador.fallo(clave)
        return render_template("login.html", form={"correo": correo_}, errores=[MENSAJE_LOGIN]), 401

    limitador.exito(clave)
    _iniciar_sesion(usuario, recordar=request.form.get("recordar") == "1")
    return redirect(url_for("cuentas.cuenta"))


@bp.post("/logout")
def logout():
    session.clear()
    flash("Cerraste sesión.", "info")
    return redirect(url_for("web.inicio"))


# ---------------------------------------------------------------------------
@bp.get("/cuenta")
@login_required
def cuenta():
    return render_template("cuenta.html", u=g.usuario, form=g.usuario.perfil | {"nombre": g.usuario.nombre},
                           errores=[], aportes=repo().mis_aportes(g.usuario.id), redes=validacion.REDES)


@bp.post("/cuenta")
@login_required
def cuenta_guardar():
    datos, errores = validacion.validar_perfil(request.form)
    if errores:
        return render_template("cuenta.html", u=g.usuario, form=datos, errores=errores,
                               aportes=repo().mis_aportes(g.usuario.id), redes=validacion.REDES), 400
    repo().actualizar_cuenta(g.usuario.id, datos)
    flash("Tus datos se guardaron.", "exito")
    return redirect(url_for("cuentas.cuenta"))


@bp.post("/cuenta/contrasena")
@login_required
def cambiar_contrasena():
    actual = request.form.get("actual") or ""
    nueva = request.form.get("nueva") or ""
    errores = []
    if not check_password_hash(g.usuario.contrasena_hash, actual[:validacion.LIMITE_PASSWORD]):
        errores.append("La contraseña actual no es correcta.")
    errores += validacion.validar_password(nueva)
    if nueva != (request.form.get("confirmar") or ""):
        errores.append("Las contraseñas nuevas no coinciden.")
    if errores:
        return render_template("cuenta.html", u=g.usuario, form=g.usuario.perfil | {"nombre": g.usuario.nombre},
                               errores_clave=errores, errores=[], aportes=repo().mis_aportes(g.usuario.id),
                               redes=validacion.REDES), 400
    repo().cambiar_contrasena(g.usuario.id, generate_password_hash(nueva))
    flash("Tu contraseña se actualizó.", "exito")
    return redirect(url_for("cuentas.cuenta"))


# ---------------------------------------------------------------------------
# Aportar una palabra o frase: queda PENDIENTE, nunca se muestra como verificada.
# ---------------------------------------------------------------------------
@bp.route("/aportar", methods=["GET", "POST"])
@login_required
def aportar():
    variante = current_app.config["VARIANTES_INICIALES"][0]
    for v in current_app.config["VARIANTES_INICIALES"]:
        if v["codigo"] == current_app.config["VARIANTE_POR_DEFECTO"]:
            variante = v
    if request.method == "GET":
        return render_template("aportar.html", variante=variante, form={}, errores=[])

    espanol, mixteco, errores = validacion.validar_aporte(request.form.get("espanol"), request.form.get("mixteco"))
    form = {"espanol": espanol, "mixteco": mixteco}
    if not errores and not current_app.limitador_aportes.permitir(g.usuario.id):
        errores = ["Alcanzaste el límite de aportes por hora. Inténtalo más tarde."]
    if errores:
        return render_template("aportar.html", variante=variante, form=form, errores=errores), 400
    nuevo = repo().crear_aporte(variante["codigo"], espanol, mixteco, validacion.tipo_de_texto(espanol), g.usuario.id)
    flash("Gracias. Tu aporte quedó pendiente de revisión por una persona hablante." if nuevo
          else "Ese aporte ya estaba registrado.", "exito" if nuevo else "info")
    return redirect(url_for("cuentas.cuenta"))


# ---------------------------------------------------------------------------
# Recuperación de contraseña por correo
# ---------------------------------------------------------------------------
@bp.route("/recuperar", methods=["GET", "POST"])
def recuperar():
    if request.method == "GET":
        return render_template("recuperar.html", paso="solicitar", errores=[])
    correo_ = (request.form.get("correo") or "").strip().lower()
    if not current_app.limitador_cuentas.permitir(_ip()):
        return render_template("recuperar.html", paso="solicitar",
                               errores=["Demasiados intentos desde esta conexión. Espera un momento."]), 429
    usuario = repo().usuario_por_correo(correo_) if validacion.PATRON_CORREO.match(correo_) else None
    if usuario and usuario.activo:
        desde = datetime.now(timezone.utc) - timedelta(hours=1)
        if repo().tokens_recientes(usuario.id, desde) < current_app.config["MAX_SOLICITUDES_RECUPERACION"]:
            token = secrets.token_urlsafe(32)
            expira = datetime.now(timezone.utc) + timedelta(minutes=current_app.config["MINUTOS_TOKEN_RECUPERACION"])
            repo().guardar_token(usuario.id, _hash_token(token), expira)
            base = current_app.config["SITIO_URL"] or request.host_url.rstrip("/")
            correo.enviar_recuperacion(current_app.config, usuario.correo, f"{base}{url_for('cuentas.nueva_contrasena', token=token)}")
    # Misma respuesta exista o no la cuenta: no se revela quién está registrado.
    return render_template("recuperar.html", paso="enviado", errores=[])


@bp.route("/recuperar/<token>", methods=["GET", "POST"])
def nueva_contrasena(token):
    hash_ = _hash_token(token[:200])
    if not repo().token_vigente(hash_):
        return render_template("recuperar.html", paso="invalido", errores=[]), 400
    if request.method == "GET":
        return render_template("recuperar.html", paso="nueva", errores=[], token=token)
    nueva = request.form.get("nueva") or ""
    errores = validacion.validar_password(nueva)
    if nueva != (request.form.get("confirmar") or ""):
        errores.append("Las contraseñas no coinciden.")
    if errores:
        return render_template("recuperar.html", paso="nueva", errores=errores, token=token), 400
    uid = repo().consumir_token(hash_)
    if uid is None:
        return render_template("recuperar.html", paso="invalido", errores=[]), 400
    repo().cambiar_contrasena(uid, generate_password_hash(nueva))
    session.clear()
    flash("Tu contraseña se actualizó. Ya puedes iniciar sesión.", "exito")
    return redirect(url_for("cuentas.login"))
