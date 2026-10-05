"""Estadisticas de la pestana Resultados y ciclo de "volvio a comprar" sin factura."""

import json
from datetime import date, timedelta

from app.config import ruta_config
from app.negocio.conexion import conectar
from app.negocio.estados import DIAS_LIMITE_FACTURA, RESULTADOS

# Facturas INVENTADAS para los clientes "DEMO - ..." (las crea y borra la herramienta datos_demo); solo
# existe mientras dura la demostracion y permite ver en Resultados como se comportan las facturas.
RUTA_COMPRAS_DEMO = ruta_config("demo_compras.json")
PREFIJO_DEMO = "DEMO - "


def resumen_seguimientos(dias=None):
    """Casos (cliente + producto) con seguimiento en los ultimos `dias` dias
    (None = todo). Cada caso trae su resultado MAS RECIENTE, para que un cliente
    que primero no contesto y luego volvio a comprar cuente solo como "volvio a
    comprar". Regresa los conteos por resultado y la lista de casos."""
    desde = (date.today() - timedelta(days=dias)).isoformat() if dias else "0000-00-00"
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT fecha, clave_cliente, codigo, resultado, proximo_recordatorio, nota FROM seguimientos "
            "WHERE fecha >= ? ORDER BY fecha ASC",
            (desde,),
        ).fetchall()
    finally:
        conn.close()

    casos = {}
    for fecha, clave, codigo, resultado, recordar, nota in filas:
        c = casos.setdefault((clave, codigo), {"seguimientos": 0, "intentos": 0})
        c["seguimientos"] += 1
        if resultado == "no_contesto":
            c["intentos"] += 1
        c.update(
            {
                "fecha": fecha,
                "clave_cliente": clave,
                "codigo": codigo,
                "resultado": resultado,
                "proximo_recordatorio": recordar,
                "nota": nota,
            }
        )
    datos = {"dias": dias, "casos": list(casos.values())}
    _recalcular_totales(datos)
    return datos


def _recalcular_totales(datos):
    """Ordena los casos (mas reciente primero) y calcula conteos y % de recuperacion."""
    lista = sorted(datos["casos"], key=lambda c: c["fecha"], reverse=True)
    totales = {r: 0 for r in RESULTADOS}
    for c in lista:
        if c["resultado"] in totales:
            totales[c["resultado"]] += 1
    decididos = totales["vendio_de_nuevo"] + totales["cambio_proveedor"]
    datos.update(
        {
            "casos": lista,
            "total": len(lista),
            "clientes": len({c["clave_cliente"] for c in lista}),
            "totales": totales,
            # De los casos ya resueltos, que porcentaje volvio a comprar
            "tasa_recuperacion": round(totales["vendio_de_nuevo"] * 100 / decididos) if decididos else None,
        }
    )


def reclasificar_por_compras(datos, compras):
    """Si en ERP hay una factura MAS NUEVA que el ultimo seguimiento de un caso
    (mismo criterio que resolver_estado), ese cliente volvio a comprar aunque nadie
    lo haya registrado: el caso pasa a "volvio a comprar" y guarda su resultado
    anterior en "antes". `compras` = {(clave_cliente, codigo): fecha_iso_ultima_compra}."""
    for c in datos["casos"]:
        compra = compras.get((c["clave_cliente"], c["codigo"]))
        if compra and c["resultado"] != "vendio_de_nuevo" and compra > c["fecha"]:
            c.update(
                {
                    "antes": c["resultado"],
                    "resultado": "vendio_de_nuevo",
                    "por_factura": True,
                    "fecha": compra,
                    "nota": None,
                    "proximo_recordatorio": None,
                }
            )
        elif c["resultado"] == "vendio_de_nuevo" and sin_factura(c["clave_cliente"], c["codigo"], c["fecha"], compras):
            c["sin_factura"] = True  # lo registraron a mano y la factura aun no aparece en ERP
            c["factura_vencida"] = (date.today() - date.fromisoformat(c["fecha"][:10])).days >= DIAS_LIMITE_FACTURA
    _recalcular_totales(datos)
    return datos


def compras_demo():
    """{(clave_cliente, codigo): fecha_iso} de las facturas inventadas de la demo ({} si no hay demo)."""
    try:
        with open(RUTA_COMPRAS_DEMO, encoding="utf-8") as f:
            return {tuple(k.split("|", 1)): v for k, v in json.load(f).items()}
    except (OSError, ValueError):
        return {}


def ventas_registradas():
    """Casos cuyo ULTIMO seguimiento es "volvio a comprar": [{clave_cliente, codigo, fecha}].
    Sirve para saber cuales siguen esperando su factura en ERP."""
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT s.clave_cliente, s.codigo, s.fecha FROM seguimientos s WHERE s.resultado = 'vendio_de_nuevo' "
            "AND s.fecha = (SELECT MAX(fecha) FROM seguimientos WHERE clave_cliente = s.clave_cliente AND codigo = s.codigo) "
            "AND s.clave_cliente NOT LIKE ? ORDER BY s.fecha",  # los clientes de la demo nunca avisan por Telegram
            (PREFIJO_DEMO + "%",),
        ).fetchall()
    finally:
        conn.close()
    return [{"clave_cliente": c, "codigo": k, "fecha": f} for c, k, f in filas]


def sin_factura(clave_cliente, codigo, fecha_seguimiento, compras):
    """True si no hay en ERP una factura mas nueva que ese seguimiento (mismo criterio
    que resolver_estado). `compras` = {(clave_cliente, codigo): fecha_iso_ultima_compra}."""
    compra = compras.get((clave_cliente, codigo))
    return not compra or compra <= fecha_seguimiento
