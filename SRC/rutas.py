"""Páginas públicas de Raíces, API del traductor y reproducción de audios autorizados."""
import logging
from pathlib import Path

from flask import Blueprint, abort, current_app, jsonify, render_template, request, send_file

from seguridad import token_csrf
from servicios.texto import validar_entrada
from servicios.tipos import ErrorProveedor

bp = Blueprint("web", __name__)
log = logging.getLogger(__name__)
POR_PAGINA = 30
TIPOS = {"palabra": "Palabras", "frase": "Frases", "oracion": "Oraciones"}


def _variantes():
    return {v["codigo"]: v for v in current_app.config["VARIANTES_INICIALES"]}


def _variante_actual():
    return _variantes()[current_app.config["VARIANTE_POR_DEFECTO"]]


@bp.get("/")
def inicio():
    return render_template("inicio.html", variante=_variante_actual(),
                           max_caracteres=current_app.config["MAX_CARACTERES"], csrf=token_csrf())


@bp.get("/ejemplos")
def ejemplos():
    variante = _variante_actual()
    codigo = variante["codigo"]
    categoria = request.args.get("categoria", "")[:40] or None
    tipo = request.args.get("tipo") if request.args.get("tipo") in TIPOS else None
    busqueda = request.args.get("q", "").strip()[:80] or None
    try:
        pagina = max(1, int(request.args.get("pagina", 1)))
    except ValueError:
        pagina = 1
    repo = current_app.repo
    entradas, total = repo.vocabulario(codigo, categoria, tipo, busqueda, pagina, POR_PAGINA)
    return render_template(
        "ejemplos.html", variante=variante, entradas=entradas, total=total, pagina=pagina,
        paginas=max(1, -(-total // POR_PAGINA)), categorias=repo.categorias_con_conteo(codigo), tipos=TIPOS,
        filtros={"categoria": categoria or "", "tipo": tipo or "", "q": busqueda or ""},
        filtros_url={k: v for k, v in (("categoria", categoria), ("tipo", tipo), ("q", busqueda)) if v},
        hay_contenido=repo.contar_verificadas(codigo) > 0)


@bp.get("/acerca")
def acerca():
    variante = _variante_actual()
    return render_template("acerca.html", variante=variante,
                           total=current_app.repo.contar_verificadas(variante["codigo"]))


@bp.get("/privacidad")
def privacidad():
    return render_template("privacidad.html", variante=_variante_actual())


@bp.post("/api/traducir")
def traducir():
    # El origen y el token CSRF ya se verificaron en app.py (antes de cada POST).
    if not current_app.limitador.permitir(request.remote_addr or "desconocida"):
        return jsonify(error="Demasiadas solicitudes. Espera un momento antes de intentar de nuevo."), 429

    datos = request.get_json(silent=True)
    if not isinstance(datos, dict):
        return jsonify(error="La solicitud no tiene el formato esperado."), 400

    texto, error = validar_entrada(datos.get("texto"), current_app.config["MAX_CARACTERES"])
    if error:
        return jsonify(error=error), 400

    codigo = datos.get("variante", current_app.config["VARIANTE_POR_DEFECTO"])
    variantes = _variantes()
    if not isinstance(codigo, str) or codigo not in variantes:
        return jsonify(error="Variante no disponible."), 400

    try:
        resultado = current_app.traductor.traducir(texto, variantes[codigo])
    except ErrorProveedor:
        # Nunca se registra el texto del usuario; ia.py ya dejó constancia del tipo de fallo.
        return jsonify(error="El servicio de traducción automática no respondió. Inténtalo de nuevo en unos minutos."), 502

    respuesta = jsonify(resultado.a_dict())
    respuesta.headers["Cache-Control"] = "no-store"
    return respuesta


@bp.get("/audio/<int:audio_id>")
def audio(audio_id):
    """Sirve un audio SOLO si está aprobado, autorizado y su traducción es visible."""
    relativa = current_app.repo.audio_ruta(audio_id)
    if not relativa:
        abort(404)
    base = Path(current_app.config["AUDIO_DIR"]).resolve()
    archivo = (base / relativa).resolve()
    if base not in archivo.parents or not archivo.is_file():     # evita rutas fuera de la carpeta
        log.error("El audio %s está aprobado pero su archivo no existe o la ruta no es válida", audio_id)
        abort(404)
    return send_file(archivo, mimetype="audio/mpeg" if archivo.suffix == ".mp3" else "audio/wav", conditional=True,
                     max_age=3600)
