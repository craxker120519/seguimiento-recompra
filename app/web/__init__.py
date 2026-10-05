"""Pagina web y API (Flask), dividida por tema en un blueprint por archivo.

- sesion:         login, logout, portada, paginas HTML y version.
- usuarios:       usuarios, contrasenas, historial de cambios y destinatarios de Telegram (administradores).
- consultas:      busqueda de productos y clientes, alertas ("Contactar hoy").
- seguimientos:   registrar y consultar seguimientos.
- configuracion:  vida util, maquinas y catalogo de filtros (al guardar dispara el aviso inmediato).
- resultados:     estadisticas de la pestana Resultados.
- exportaciones:  todos los Excel.
- comun:          ayudas compartidas (nombres de producto, resultados con facturas nuevas).

Todo exige sesion salvo /login y los archivos estaticos. Las paginas estan en app/static/.
"""

import os
import secrets

from flask import Flask, jsonify, redirect, request, session, url_for

from app.config import ruta_config
from app.web import configuracion, consultas, exportaciones, resultados, seguimientos, sesion, usuarios

RUTAS_PUBLICAS = {"sesion.login", "static"}
BLUEPRINTS = (sesion, usuarios, consultas, seguimientos, configuracion, resultados, exportaciones)


def _cargar_secret_key():
    """La llave que firma las sesiones: se lee de config/secret_key.txt y se crea sola la primera vez."""
    ruta = ruta_config("secret_key.txt")
    if os.path.exists(ruta):
        with open(ruta, encoding="utf-8") as f:
            return f.read().strip()
    clave = secrets.token_hex(32)
    with open(ruta, "w", encoding="utf-8") as f:
        f.write(clave)
    return clave


def crear_app():
    app = Flask(
        __name__, static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), "static"), static_url_path=""
    )
    app.config.update(
        SESSION_COOKIE_SECURE=True,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    app.secret_key = _cargar_secret_key()

    @app.before_request
    def requerir_login():
        if request.endpoint in RUTAS_PUBLICAS or request.endpoint is None:
            return None
        if "usuario_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "no autenticado"}), 401
            return redirect(url_for("sesion.login"))
        return None

    for modulo in BLUEPRINTS:
        app.register_blueprint(modulo.bp)
    return app
