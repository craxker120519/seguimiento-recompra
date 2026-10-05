"""Usuarios, contrasenas, historial de cambios y destinatarios de Telegram."""

from flask import Blueprint, jsonify, request, session

from app import auth, negocio

bp = Blueprint("usuarios", __name__)

BOT_TELEGRAM_USUARIO = "filtros_demo_bot"


def _es_admin():
    return session.get("usuario_rol") == "admin"


@bp.route("/api/usuarios", methods=["GET", "POST"])
def api_usuarios():
    if request.method == "GET":
        return jsonify(auth.listar_usuarios())
    if not _es_admin():
        return jsonify({"error": "solo un administrador puede crear usuarios"}), 403
    data = request.get_json(force=True)
    nombre = data.get("nombre", "").strip()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    rol = data.get("rol") or "vendedor"
    if not nombre or not username or not password:
        return jsonify({"error": "faltan campos"}), 400
    try:
        auth.crear_usuario(nombre, username, password, rol=rol)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.route("/api/cambiar-password", methods=["POST"])
def api_cambiar_password():
    data = request.get_json(force=True)
    actual = data.get("password_actual", "")
    nueva = data.get("password_nueva", "")
    if not actual or not nueva:
        return jsonify({"error": "faltan campos"}), 400
    username = session.get("usuario_username")
    motivo = auth.validar_password(nueva, username)
    if motivo:
        return jsonify({"error": motivo}), 400
    if not username or not auth.cambiar_password(username, actual, nueva):
        return jsonify({"error": "la contraseña actual no es correcta"}), 400
    return jsonify({"ok": True})


@bp.route("/api/usuarios/<int:usuario_id>/password", methods=["POST"])
def api_usuario_establecer_password(usuario_id):
    if not _es_admin():
        return jsonify({"error": "solo un administrador puede cambiar contraseñas"}), 403
    data = request.get_json(force=True)
    nueva = data.get("password_nueva", "")
    usuario = next((u for u in auth.listar_usuarios() if u["id"] == usuario_id), None)
    if not usuario:
        return jsonify({"error": "ese usuario no existe"}), 404
    motivo = auth.validar_password(nueva, usuario["username"])
    if motivo:
        return jsonify({"error": motivo}), 400
    auth.establecer_password(usuario["username"], nueva)
    return jsonify({"ok": True})


@bp.route("/api/historial-config")
def api_historial_config():
    if not _es_admin():
        return jsonify({"error": "solo un administrador puede ver el historial"}), 403
    return jsonify(negocio.historial_config())


@bp.route("/api/telegram/chats", methods=["GET"])
def api_telegram_chats():
    return jsonify(negocio.listar_chats_telegram())


@bp.route("/api/telegram/chats/<chat_id>", methods=["DELETE"])
def api_telegram_chats_borrar(chat_id):
    if not _es_admin():
        return jsonify({"error": "solo un administrador puede quitar destinatarios"}), 403
    negocio.quitar_chat_telegram(chat_id)
    return jsonify({"ok": True})


@bp.route("/api/telegram/invitar", methods=["POST"])
def api_telegram_invitar():
    if not _es_admin():
        return jsonify({"error": "solo un administrador puede generar invitaciones"}), 403
    data = request.get_json(force=True)
    usuario_id = data.get("usuario_id")
    if not usuario_id:
        return jsonify({"error": "falta usuario_id"}), 400
    usuario = next((u for u in auth.listar_usuarios() if u["id"] == usuario_id), None)
    if not usuario:
        return jsonify({"error": "ese usuario no existe"}), 404
    ya_enlazados = {c["usuario_id"] for c in negocio.listar_chats_telegram() if c["usuario_id"]}
    if usuario_id in ya_enlazados:
        return jsonify({"error": "ese usuario ya tiene Telegram enlazado"}), 400
    token = negocio.crear_invitacion_telegram(usuario["nombre"], usuario_id=usuario_id)
    link = f"https://t.me/{BOT_TELEGRAM_USUARIO}?start={token}"
    return jsonify({"nombre": usuario["nombre"], "link": link})
