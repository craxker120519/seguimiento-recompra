"""Login, logout, portada y paginas HTML."""

import os

from flask import Blueprint, Response, current_app, jsonify, redirect, request, session, url_for

from app import auth, negocio
from app.config import ARCHIVO_VERSION

bp = Blueprint("sesion", __name__)


def _version():
    try:
        with open(ARCHIVO_VERSION, encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return None


def _pagina(nombre):
    """Sirve una pagina de app/static poniendo la version en los enlaces a css/js (asi el navegador
    baja los archivos nuevos despues de cada despliegue y no usa copias viejas)."""
    with open(os.path.join(current_app.static_folder, nombre), encoding="utf-8") as f:
        html = f.read().replace("__VERSION__", _version() or "0")
    respuesta = Response(html, mimetype="text/html")
    respuesta.headers["Cache-Control"] = "no-cache"
    return respuesta


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return _pagina("login.html")
    username = request.form.get("username", "")
    password = request.form.get("password", "")
    minutos = negocio.esta_bloqueado(username)
    if minutos:
        return redirect(url_for("sesion.login", error="bloqueado", minutos=minutos))
    usuario = auth.verificar_usuario(username, password)
    if not usuario:
        negocio.registrar_intento_fallido(username)
        return redirect(url_for("sesion.login", error="1"))
    negocio.limpiar_intentos(username)
    session["usuario_id"] = usuario["id"]
    session["usuario_nombre"] = usuario["nombre"]
    session["usuario_rol"] = usuario["rol"]
    session["usuario_username"] = usuario["username"]
    return redirect(url_for("sesion.index"))


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("sesion.login"))


@bp.route("/api/sesion")
def api_sesion():
    return jsonify({"nombre": session.get("usuario_nombre"), "rol": session.get("usuario_rol")})


@bp.route("/")
def index():
    return _pagina("index.html")


@bp.route("/usuarios")
def usuarios_page():
    return _pagina("usuarios.html")


@bp.route("/api/version")
def api_version():
    return jsonify({"version": _version()})
