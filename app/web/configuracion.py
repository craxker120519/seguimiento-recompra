"""Vida util, maquinas y catalogo de filtros. Al guardar vida util o maquinas se manda el aviso inmediato."""

import threading

from flask import Blueprint, current_app, jsonify, request, session

from app import negocio
from app.erp import buscar_catalogo_erp, catalogo_filtros
from app.negocio.filtros import codigos_filtro
from app.telegram import avisos

bp = Blueprint("configuracion", __name__)


def _avisar_en_segundo_plano(codigo, clave_cliente=None):
    """Aviso inmediato por Telegram tras capturar vida util o maquinas. Va en
    un hilo aparte para no hacer lenta la respuesta, y un fallo de Telegram
    o de la base de ERP nunca debe afectar el guardado."""
    logger = current_app.logger

    def tarea():
        try:
            avisos.avisar_alertas(codigo, clave_cliente)
        except Exception:
            logger.exception("no se pudo mandar el aviso inmediato de Telegram")

    threading.Thread(target=tarea, daemon=True).start()


@bp.route("/api/vida-util", methods=["POST"])
def api_set_vida_util():
    data = request.get_json(force=True)
    codigo = data.get("codigo")
    meses = data.get("meses")
    if not codigo or meses is None:
        return jsonify({"error": "falta codigo o meses"}), 400
    try:
        meses = float(meses)
        negocio.set_vida_util(codigo, meses)
        negocio.registrar_cambio_config("vida_util", codigo, None, meses, session.get("usuario_nombre"))
        _avisar_en_segundo_plano(codigo)
        return jsonify({"codigo": codigo, "meses": meses})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/maquinas", methods=["POST"])
def api_set_maquinas():
    data = request.get_json(force=True)
    clave_cliente = data.get("clave_cliente")
    codigo = data.get("codigo")
    cantidad = data.get("cantidad")
    if not clave_cliente or not codigo or cantidad is None:
        return jsonify({"error": "falta clave_cliente, codigo o cantidad"}), 400
    try:
        cantidad = int(cantidad)
        negocio.set_maquinas(clave_cliente, codigo, cantidad)
        negocio.registrar_cambio_config("maquinas", codigo, clave_cliente, cantidad, session.get("usuario_nombre"))
        _avisar_en_segundo_plano(codigo, clave_cliente)
        return jsonify({"clave_cliente": clave_cliente, "codigo": codigo, "cantidad": cantidad})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/catalogo")
def api_catalogo():
    try:
        return jsonify(catalogo_filtros(codigos_filtro(), con_vida_util=True))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/catalogo/buscar")
def api_catalogo_buscar():
    texto = request.args.get("q", "").strip()
    if len(texto) < 2:
        return jsonify([])
    try:
        return jsonify(buscar_catalogo_erp(texto, codigos_filtro()))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@bp.route("/api/catalogo/agregar", methods=["POST"])
def api_catalogo_agregar():
    data = request.get_json(force=True)
    codigo = data.get("codigo")
    if not codigo:
        return jsonify({"error": "falta codigo"}), 400
    try:
        negocio.agregar_filtro(codigo)
        return jsonify({"codigo": codigo})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
