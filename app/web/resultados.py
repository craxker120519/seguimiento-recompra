"""Pestana Resultados: casos con seguimiento y sus resultados."""

from flask import Blueprint, jsonify

from app.web.comun import datos_resultados, dias_de_la_peticion, nombres_producto

bp = Blueprint("resultados", __name__)


@bp.route("/api/resultados")
def api_resultados():
    """Casos con seguimiento y sus resultados: ?dias=30|90|365 (sin dias = todo)."""
    dias, valido = dias_de_la_peticion()
    if not valido:
        return jsonify({"error": "dias debe ser positivo"}), 400
    datos = datos_resultados(dias)
    nombres = nombres_producto()
    for c in datos["casos"]:
        c["nombre_producto"] = nombres.get(c["codigo"], "")
    return jsonify(datos)
