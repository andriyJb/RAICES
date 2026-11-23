"""Raíces · traductor español → mixteco.

Archivo principal: crea la aplicación y levanta el servidor local.

    cd SRC
    python app.py                          # http://127.0.0.1:5000
    flask --app app init-db                # crea las tablas y la variante inicial (desarrollo)
    flask --app app asignar-rol correo hablante

En producción: gunicorn "app:create_app()"  (ver docs/despliegue_google_cloud.md)
"""
import logging
import secrets

import click
from flask import Flask, flash, g, jsonify, redirect, render_template, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from config import Config
from extensions import db
from seguridad import LimitadorFallos, LimitadorVentana, aplicar_cabeceras, csrf_valido, origen_valido, token_csrf

MENSAJES_ERROR = {
    400: "La solicitud no es válida.",
    403: "No tienes permiso para ver esta página.",
    404: "No encontramos la página que buscas.",
    405: "Esta acción no está permitida.",
    413: "La solicitud es demasiado grande.",
    429: "Demasiadas solicitudes. Espera un momento.",
    500: "Ocurrió un error inesperado. Inténtalo de nuevo más tarde.",
    503: "El servicio no está disponible por el momento. Inténtalo de nuevo en unos minutos.",
}


def create_app(configuracion=None, repo=None):
    """`repo` permite sustituir el acceso a la base de datos (las pruebas usan uno en memoria)."""
    app = Flask(__name__)
    app.config.from_object(Config)
    if configuracion:
        app.config.update(configuracion)

    produccion = app.config["ENTORNO"] == "production"
    if not app.config.get("SECRET_KEY"):
        if produccion:
            raise RuntimeError("Falta SECRET_KEY en el entorno (.env).")
        app.config["SECRET_KEY"] = secrets.token_hex(32)  # solo desarrollo
    if app.config["VARIANTE_POR_DEFECTO"] not in {v["codigo"] for v in app.config["VARIANTES_INICIALES"]}:
        raise RuntimeError("VARIANTE_POR_DEFECTO no existe en VARIANTES_INICIALES.")

    if app.config["PROXY_SALTOS"] > 0:  # detrás de un proxy (Cloud Run: 1)
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=app.config["PROXY_SALTOS"], x_proto=app.config["PROXY_SALTOS"])

    db.init_app(app)
    autoinicio = repo is None
    if repo is None:
        from servicios import repositorio as repo
    app.repo = repo

    # Motor de traducción. Si se elige un proveedor sin su clave, falla AL ARRANCAR con el nombre exacto.
    from servicios.filtro import crear_filtro
    from servicios.ia import PROVEEDORES, crear_proveedor
    from servicios.traductor import Traductor
    nombre_ia = app.config["PROVEEDOR_IA"]
    if nombre_ia in PROVEEDORES and not app.config.get(PROVEEDORES[nombre_ia][1]):
        # Sin clave la app arranca igual, con la IA desactivada (la página lo indica).
        app.logger.warning("PROVEEDOR_IA=%s pero falta %s en .env: la traducción automática queda DESACTIVADA.",
                           nombre_ia, PROVEEDORES[nombre_ia][1])
        app.config["PROVEEDOR_IA"] = "ninguno"
    try:
        proveedor = crear_proveedor(app.config)
    except ValueError as e:       # p. ej. un nombre de proveedor mal escrito
        raise RuntimeError(str(e)) from None
    app.traductor = Traductor(repo, proveedor, crear_filtro(app.config["IA_ESTRICTO"]) if proveedor else None,
                              app.config["LIMITE_DIARIO_IA"], depurar=app.config["ENTORNO"] == "development")

    app.limitador = LimitadorVentana(app.config["LIMITE_SOLICITUDES"], app.config["VENTANA_SEGUNDOS"])
    app.limitador_login = LimitadorFallos(app.config["MAX_INTENTOS_LOGIN"], app.config["BLOQUEO_LOGIN_SEGUNDOS"])
    app.limitador_cuentas = LimitadorVentana(20, 3600)       # registros y recuperaciones por IP y hora
    app.limitador_aportes = LimitadorVentana(app.config["MAX_APORTES_POR_HORA"], 3600)

    import cuentas
    from rutas import bp
    app.register_blueprint(bp)
    app.register_blueprint(cuentas.bp)

    @app.before_request
    def proteger_y_cargar_usuario():
        # CSRF y origen en TODO POST (formularios y fetch).
        if request.method == "POST" and (not origen_valido() or not csrf_valido()):
            if request.path.startswith("/api/"):
                return jsonify(error="Solicitud no válida. Recarga la página e inténtalo de nuevo."), 400
            flash("La sesión del formulario venció. Inténtalo de nuevo.", "error")
            return redirect(request.referrer or url_for("web.inicio"))
        cuentas.cargar_usuario()

    @app.context_processor
    def datos_globales():
        return {"ia_activa": app.traductor.ia_activa, "ia_proveedor": app.config["PROVEEDOR_IA"], "usuario": g.get("usuario"), "csrf": token_csrf()}

    @app.after_request
    def cabeceras(respuesta):
        return aplicar_cabeceras(respuesta, produccion)

    def manejar_error(error):
        codigo = getattr(error, "code", 500)
        mensaje = MENSAJES_ERROR.get(codigo, MENSAJES_ERROR[500])
        if request.path.startswith("/api/"):
            return jsonify(error=mensaje), codigo
        return render_template("error.html", codigo=codigo, mensaje=mensaje), codigo

    for codigo in MENSAJES_ERROR:
        app.register_error_handler(codigo, manejar_error)

    try:
        from sqlalchemy.exc import SQLAlchemyError

        @app.errorhandler(SQLAlchemyError)
        def error_bd(error):
            db.session.rollback()
            # Se registra el mensaje del controlador (p. ej. «no such table: uso_ia»), NO la sentencia SQL,
            # porque esta puede incluir el texto que escribió el usuario.
            causa = getattr(error, "orig", None)
            detalle = f"{type(causa).__name__}: {str(causa)[:200]}" if causa is not None else type(error).__name__
            app.logger.error("Error de base de datos en %s %s → %s", request.method, request.path, detalle)
            return manejar_error(type("E", (), {"code": 503})())
    except ImportError:    # solo en entornos sin SQLAlchemy (pruebas con repositorio en memoria)
        pass

    def _informe_esquema():
        import models  # noqa: F401  (registra las tablas en db.metadata)
        from servicios import esquema
        with app.app_context():
            return esquema.informe(db.engine, db.metadata)

    def inicializar_bd():
        """Crea las tablas que falten y registra las variantes iniciales. No borra nada."""
        from models import Variante
        db.create_all()
        for datos in app.config["VARIANTES_INICIALES"]:
            if not Variante.query.filter_by(codigo=datos["codigo"]).first():
                db.session.add(Variante(**datos))
        db.session.commit()

    @app.cli.command("init-db")
    def init_db():
        """Crea las tablas y registra las variantes iniciales (desarrollo; en producción usa migraciones)."""
        inicializar_bd()
        avisos = _informe_esquema()
        print(avisos or "Base de datos lista y alineada con los modelos.")
        if avisos:
            raise SystemExit(1)

    @app.cli.command("revisar-bd")
    def revisar_bd():
        """Compara las tablas y columnas de la base de datos con los modelos."""
        avisos = _informe_esquema()
        print(avisos or "La base de datos coincide con los modelos (tablas y columnas).")
        if avisos:
            raise SystemExit(1)

    # Comodidad en local: con el SQLite de desarrollo las tablas se crean solas al arrancar.
    if (autoinicio and not app.config["TESTING"] and app.config["ENTORNO"] == "development"
            and app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite")):
        try:
            with app.app_context():
                inicializar_bd()
        except Exception as e:      # no impide arrancar; init-db muestra el detalle
            app.logger.error("No se pudo inicializar la base de datos automáticamente (%s).", type(e).__name__)

    @app.cli.command("asignar-rol")
    @click.argument("correo")
    @click.argument("rol")
    def asignar_rol(correo, rol):
        """Asigna el rol de una cuenta: flask asignar-rol correo@ejemplo.com hablante  (usuario | hablante)."""
        from models import ROLES
        if rol not in ROLES:
            raise click.UsageError(f"El rol debe ser uno de: {', '.join(ROLES)}")
        print("Rol asignado." if app.repo.asignar_rol(correo.strip().lower(), rol) else "No existe esa cuenta.")

    if autoinicio and not app.config["TESTING"]:
        try:
            aviso = _informe_esquema()
            if aviso:
                app.logger.error("\n%s", aviso)
        except Exception as e:     # p. ej. MySQL apagado: no impide arrancar
            app.logger.error("No se pudo comprobar la estructura de la base de datos (%s).", type(e).__name__)

    try:
        from flask_migrate import Migrate
        Migrate(app, db)       # habilita `flask db init / migrate / upgrade`
    except ImportError:
        pass

    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    aplicacion = create_app()
    aplicacion.run(host="127.0.0.1", port=5000, debug=aplicacion.config["ENTORNO"] == "development")
