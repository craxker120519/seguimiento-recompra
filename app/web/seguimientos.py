"""Registrar y consultar seguimientos."""

from flask import Blueprint, jsonify, request, session

from app import negocio

bp = Blueprint("seguimientos", __name__)


@bp.route("/api/seguimiento", methods=["GET", "POST"])
def api_seguimiento():
    if request.method == "GET":
        clave_cliente = request.args.get("clave_cliente", "")
        codigo = request.args.get("codigo", "")
        if not clave_cliente or not codigo:
            return jsonify({"error": "falta clave_cliente o codigo"}), 400
        return jsonify(negocio.historial_seguimiento(clave_cliente, codigo))
    data = request.get_json(force=True)
    clave_cliente = data.get("clave_cliente")
    codigo = data.get("codigo")
    resultado = data.get("resultado")
    proximo_recordatorio = data.get("proximo_recordatorio")
    nota = data.get("nota")
    if not clave_cliente or not codigo or resultado not in negocio.RESULTADOS:
        return jsonify({"error": "faltan campos o resultado inválido"}), 400
    if resultado == "contactado_esperar" and not proximo_recordatorio:
        return jsonify({"error": "falta la fecha de proximo_recordatorio"}), 400
    if resultado == "no_aplica" and len((nota or "").strip()) < 3:
        return jsonify({"error": "escribe el motivo por el que no aplica"}), 400
    # "No aplica" puede ir a todos los productos del cliente (p. ej. cerro la empresa)
    codigos = [codigo]
    if resultado == "no_aplica" and isinstance(data.get("codigos"), list):
        codigos = list(dict.fromkeys([codigo] + [str(c) for c in data["codigos"] if c]))
    try:
        for c in codigos:
            negocio.registrar_seguimiento(
                clave_cliente, c, resultado, proximo_recordatorio, nota, session.get("usuario_nombre")
            )
        return jsonify({"ok": True, "registrados": len(codigos)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
