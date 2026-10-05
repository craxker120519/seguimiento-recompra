"""Ultima compra de cada cliente y filtro, y la lista de trabajo del dia (alertas de recontacto)."""

from datetime import date, timedelta

from app import negocio
from app.erp.catalogo import catalogo_filtros
from app.erp.conexion import (
    ACTUAL_DB,
    ACTUAL_DOCUMENT_TYPE_ID,
    ACTUAL_MODULE_ID,
    FECHA_INICIO,
    LEGACY_CONCEPTOS_FACTURA,
    LEGACY_DB,
    conectar,
    normalizar_nombre,
    temp_codigos,
)


def _ultima_compra_por_cliente_legacy(codigos):
    """Última compra de cada combinación cliente+filtro (solo esa fila,
    vía ROW_NUMBER), para no traer todo el historial completo."""
    conn = conectar(LEGACY_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos, collate="Modern_Spanish_CI_AS")
        placeholders = ",".join(str(x) for x in LEGACY_CONCEPTOS_FACTURA)
        cur.execute(
            f"""
            SELECT Cliente, Codigo, Fecha, Unidades FROM (
                SELECT d.CIDCLIENTEPROVEEDOR ClienteId, d.CRAZONSOCIAL Cliente, f.Codigo,
                       d.CFECHA Fecha, m.CUNIDADES Unidades,
                       ROW_NUMBER() OVER (PARTITION BY d.CIDCLIENTEPROVEEDOR, f.Codigo ORDER BY d.CFECHA DESC) Rn
                FROM admMovimientos m
                JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
                JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
                JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
                WHERE d.CIDCONCEPTODOCUMENTO IN ({placeholders})
                  AND d.CCANCELADO = 0
                  AND d.CFECHA >= ?
            ) x
            WHERE Rn = 1
        """,
            FECHA_INICIO,
        )
        return [
            {"cliente": r.Cliente, "codigo": r.Codigo, "fecha": r.Fecha.isoformat(), "unidades": float(r.Unidades or 0)}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def _ultima_compra_por_cliente_actual(codigos):
    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos)
        cur.execute(
            """
            SELECT Cliente, Codigo, Fecha, Unidades FROM (
                SELECT d.BusinessEntityID ClienteId,
                       COALESCE(NULLIF(be.CommercialName, ''), be.OfficialName) Cliente,
                       f.Codigo, d.DateDocument Fecha, di.Quantity Unidades,
                       ROW_NUMBER() OVER (PARTITION BY d.BusinessEntityID, f.Codigo ORDER BY d.DateDocument DESC) Rn
                FROM docDocumentItem di
                JOIN docDocument d ON d.DocumentID = di.DocumentID
                JOIN orgBusinessEntity be ON be.BusinessEntityID = d.BusinessEntityID
                JOIN #Filtros f ON f.Codigo = di.ProductKey
                WHERE d.ModuleID = ? AND d.DocumentTypeID = ?
                  AND d.CancelledOn IS NULL
                  AND d.DateDocument >= ?
            ) x
            WHERE Rn = 1
        """,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            FECHA_INICIO,
        )
        return [
            {"cliente": r.Cliente, "codigo": r.Codigo, "fecha": r.Fecha.isoformat(), "unidades": float(r.Unidades or 0)}
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def ultimas_compras_por_cliente(codigos):
    """Ultima compra de cada cliente y filtro, de ambas bases: [{cliente, codigo, fecha, unidades}]."""
    return _ultima_compra_por_cliente_legacy(codigos) + _ultima_compra_por_cliente_actual(codigos)


def ultimas_compras(codigos):
    """{(clave_cliente, codigo): fecha_iso} de la compra mas reciente de cada
    cliente+filtro, juntando las dos bases de ERP."""
    filas = ultimas_compras_por_cliente(codigos)
    compras = {}
    for f in filas:
        clave = normalizar_nombre(f["cliente"])
        if clave and f["fecha"] > compras.get((clave, f["codigo"]), ""):
            compras[(clave, f["codigo"])] = f["fecha"]
    compras.update(negocio.compras_demo())
    return compras


def alertas_recontacto(codigos, incluir_esperando_factura=False):
    """Para cada combinación cliente+filtro, la fecha estimada de próximo
    contacto según su compra más reciente; solo regresa las que ya están
    vencidas o vencen dentro de los próximos 7 días (mismo criterio que
    el badge naranja/rojo del frontend).

    "Volvió a comprar" sin factura: pasada la semana de prórroga aparece como
    estado "esperando_factura" (solo con incluir_esperando_factura=True, para
    mostrarlo en la pestaña; no hay que contactar todavía) y al día 15 pasa a
    "factura_vencida", que sí es una alerta normal: hay que contactar al cliente."""
    filas = ultimas_compras_por_cliente(codigos)

    combinadas = {}
    for f in filas:
        clave_cliente = normalizar_nombre(f["cliente"])
        if not clave_cliente:
            continue
        clave = (clave_cliente, f["codigo"])
        actual = combinadas.get(clave)
        if actual is None or f["fecha"] > actual["fecha"]:
            combinadas[clave] = {**f, "clave_cliente": clave_cliente}

    vida_util = negocio.listar_vida_util()
    maquinas = negocio.listar_maquinas()

    hoy = date.today().isoformat()
    limite = (date.today() + timedelta(days=7)).isoformat()

    resultado = []
    nombres_producto = {p["codigo"]: p["nombre"] for p in catalogo_filtros(codigos)}
    for (clave_cliente, codigo), f in combinadas.items():
        meses = vida_util.get(codigo)
        cant_maquinas = maquinas.get((clave_cliente, codigo))
        estado = negocio.resolver_estado(clave_cliente, codigo, f["fecha"], f["unidades"], meses, cant_maquinas)
        if estado["estado"] in ("resuelto", "inactivo", "descartado"):
            continue
        proximo = estado["proximo_contacto"]
        if estado["estado"] == "esperando_factura":
            dias_sin_factura = (date.today() - date.fromisoformat(estado["nota"])).days
            if not incluir_esperando_factura or dias_sin_factura < negocio.DIAS_PRORROGA_FACTURA:
                continue
        elif not proximo or proximo > limite:
            continue
        resultado.append(
            {
                "cliente": f["cliente"],
                "clave_cliente": clave_cliente,
                "codigo": codigo,
                "nombre_producto": nombres_producto.get(codigo, codigo),
                "ultima_compra": f["fecha"],
                "proximo_contacto": proximo,
                "vencido": proximo < hoy,
                "estado": estado["estado"],
                "nota_estado": estado["nota"],
            }
        )

    resultado.sort(key=lambda a: a["proximo_contacto"])
    return resultado
