"""Reglas que deciden el estado de cada caso (cliente + filtro).

- calcular_proximo_contacto: fecha de compra + (piezas / maquinas * vida util) * 30.44 dias.
- resolver_estado: combina la ultima compra con el ultimo seguimiento. Un seguimiento solo cuenta si es
  posterior a la ultima compra. Estados: normal, pendiente, reintentar, inactivo, descartado,
  esperando_factura y factura_vencida (ver docs/ARQUITECTURA.md).
"""

from datetime import date, datetime, timedelta

from app.negocio.seguimientos import ultimo_seguimiento

DIAS_POR_MES = 30.44
DIAS_REINTENTO = 3  # tras un "No contesto", cuantos dias despues se vuelve a intentar
# "Volvio a comprar" registrado a mano sin factura en ERP: la primera semana es de prorroga (sin
# aviso), de ahi al dia 15 se avisa cada semana ("esperando factura") y al dia 15 pasa a vencido:
# hay que contactar al cliente. Un seguimiento nuevo reinicia el ciclo.
DIAS_PRORROGA_FACTURA = 7
DIAS_LIMITE_FACTURA = 15

RESULTADOS = ("contactado_esperar", "vendio_de_nuevo", "cambio_proveedor", "no_contesto", "no_aplica")


def calcular_proximo_contacto(fecha_compra_iso, unidades, meses, maquinas):
    """fecha_compra + (unidades/maquinas * meses de vida util), en días
    aproximados (30.44 dias/mes). Regresa None si falta vida util o maquinas."""
    if not meses or not maquinas:
        return None
    filtros_por_maquina = unidades / maquinas
    meses_cobertura = filtros_por_maquina * meses
    fecha = datetime.fromisoformat(fecha_compra_iso).date()
    return (fecha + timedelta(days=round(meses_cobertura * DIAS_POR_MES))).isoformat()


def resolver_estado(clave_cliente, codigo, fecha_compra_iso, unidades, meses, maquinas):
    """Envuelve calcular_proximo_contacto ajustándolo según el último
    seguimiento registrado (si aplica a este ciclo de compra)."""
    calculado = calcular_proximo_contacto(fecha_compra_iso, unidades, meses, maquinas)
    seguimiento = ultimo_seguimiento(clave_cliente, codigo) if clave_cliente else None

    if seguimiento and seguimiento["fecha"] >= fecha_compra_iso:
        resultado = seguimiento["resultado"]
        if resultado == "contactado_esperar":
            return {"proximo_contacto": seguimiento["proximo_recordatorio"], "estado": "pendiente", "nota": None}
        if resultado == "vendio_de_nuevo":
            # Llega aqui solo si NO hay factura mas nueva que el seguimiento (si la hubiera, el
            # seguimiento se ignora y el ciclo se calcula con esa factura).
            desde = seguimiento["fecha"][:10]
            limite = (date.fromisoformat(desde) + timedelta(days=DIAS_LIMITE_FACTURA)).isoformat()
            estado = "factura_vencida" if limite <= date.today().isoformat() else "esperando_factura"
            return {"proximo_contacto": limite, "estado": estado, "nota": desde}
        if resultado == "cambio_proveedor":
            return {"proximo_contacto": None, "estado": "inactivo", "nota": seguimiento["nota"]}
        if resultado == "no_aplica":
            # Descartado a proposito (cerro la empresa, ya no usa el filtro, la venta no se facturara...):
            # sin alertas ni avisos. Un seguimiento nuevo, o una factura mas nueva en ERP, lo reactiva.
            return {"proximo_contacto": None, "estado": "descartado", "nota": seguimiento["nota"]}
        if resultado == "no_contesto":
            desde = seguimiento["fecha"][:10]
            reintento = (date.fromisoformat(desde) + timedelta(days=DIAS_REINTENTO)).isoformat()
            return {"proximo_contacto": reintento, "estado": "reintentar", "nota": desde}

    return {"proximo_contacto": calculado, "estado": "normal", "nota": None}
