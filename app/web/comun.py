"""Ayudas compartidas por varios modulos de la web."""

from flask import request

from app import negocio
from app.erp import catalogo_filtros, ultimas_compras
from app.negocio.filtros import codigos_filtro

ETIQUETAS_RESULTADO = {
    "contactado_esperar": "Pidió esperar",
    "vendio_de_nuevo": "Volvió a comprar",
    "cambio_proveedor": "Cambió de proveedor",
    "no_contesto": "No contestó",
    "no_aplica": "No aplica",
}


def nombres_producto():
    """{codigo: nombre} de los filtros; sin conexion a ERP regresa {} y se muestra solo el codigo."""
    try:
        return {p["codigo"]: p["nombre"] for p in catalogo_filtros(codigos_filtro())}
    except Exception:
        return {}


def datos_resultados(dias):
    """Resumen de seguimientos al que se le aplican las facturas nuevas de ERP:
    quien volvio a comprar despues de su ultimo seguimiento cuenta como recuperado."""
    datos = negocio.resumen_seguimientos(dias)
    try:
        negocio.reclasificar_por_compras(datos, ultimas_compras(codigos_filtro()))
    except Exception:
        pass  # sin conexion a ERP se muestra lo que dicen los seguimientos
    return datos


def dias_de_la_peticion():
    """Lee ?dias= de la peticion. Regresa (dias, valido): sin el parametro es (None, True) = todo el historial."""
    dias = request.args.get("dias", type=int)
    if dias is None:
        return None, True
    return (dias, True) if dias > 0 else (None, False)
