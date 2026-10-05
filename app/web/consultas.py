"""Consultas de solo lectura sobre ERP: productos, clientes y alertas ("Contactar hoy")."""

from flask import Blueprint, jsonify, request

from app.erp import (
    alertas_recontacto,
    buscar_clientes,
    catalogo_filtros,
    resumen_combinado,
    timeline_cliente,
    timeline_producto,
)
from app.negocio.filtros import codigos_filtro

bp = Blueprint("consultas", __name__)


@bp.route("/api/resumen")
def api_resumen():
    try:
        return jsonify(resumen_combinado(codigos_filtro()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/productos")
def api_productos():
    try:
        return jsonify(catalogo_filtros(codigos_filtro()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/producto/<codigo>")
def api_producto(codigo):
    try:
        return jsonify(timeline_producto(codigo))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/alertas")
def api_alertas():
    try:
        return jsonify(alertas_recontacto(codigos_filtro(), incluir_esperando_factura=True))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/clientes")
def api_clientes():
    texto = request.args.get("q", "").strip()
    if len(texto) < 2:
        return jsonify([])
    try:
        return jsonify(buscar_clientes(texto, codigos_filtro()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/cliente")
def api_cliente():
    legacy_id = request.args.get("legacy_id", type=int)
    actual_id = request.args.get("actual_id", type=int)
    if legacy_id is None and actual_id is None:
        return jsonify({"error": "falta legacy_id o actual_id"}), 400
    try:
        return jsonify(timeline_cliente(codigos_filtro(), legacy_id=legacy_id, actual_id=actual_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500
