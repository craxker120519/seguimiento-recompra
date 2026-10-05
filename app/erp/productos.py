"""Ventas por producto: resumen general y linea de tiempo de un filtro (todos sus clientes)."""

from datetime import date

from app import negocio
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


def _resumen_legacy(codigos):
    conn = conectar(LEGACY_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos, collate="Modern_Spanish_CI_AS")
        placeholders = ",".join(str(x) for x in LEGACY_CONCEPTOS_FACTURA)

        # CTOTAL viene en la moneda del documento (CIDMONEDA); multiplicar por
        # CTIPOCAMBIO lo convierte siempre a pesos (para documentos en pesos
        # el tipo de cambio ya está guardado como 1.0).
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT d.CIDDOCUMENTO) Facturas, SUM(m.CUNIDADES) Unidades,
                   SUM(m.CTOTAL * d.CTIPOCAMBIO) Monto
            FROM admMovimientos m
            JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
            JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
            JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
            WHERE d.CIDCONCEPTODOCUMENTO IN ({placeholders})
              AND d.CCANCELADO = 0
              AND d.CFECHA >= ?
        """,
            FECHA_INICIO,
        )
        total = cur.fetchone()

        cur.execute(
            f"""
            SELECT FORMAT(d.CFECHA, 'yyyy-MM') Mes, SUM(m.CUNIDADES) Unidades,
                   SUM(m.CTOTAL * d.CTIPOCAMBIO) Monto
            FROM admMovimientos m
            JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
            JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
            JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
            WHERE d.CIDCONCEPTODOCUMENTO IN ({placeholders})
              AND d.CCANCELADO = 0
              AND d.CFECHA >= ?
            GROUP BY FORMAT(d.CFECHA, 'yyyy-MM')
        """,
            FECHA_INICIO,
        )
        por_mes = [(r.Mes, float(r.Unidades or 0), float(r.Monto or 0)) for r in cur.fetchall()]

        cur.execute(
            f"""
            SELECT f.Codigo, MAX(RTRIM(p.CNOMBREPRODUCTO)) Nombre,
                   SUM(m.CUNIDADES) Unidades, SUM(m.CTOTAL * d.CTIPOCAMBIO) Monto
            FROM admMovimientos m
            JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
            JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
            JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
            WHERE d.CIDCONCEPTODOCUMENTO IN ({placeholders})
              AND d.CCANCELADO = 0
              AND d.CFECHA >= ?
            GROUP BY f.Codigo
        """,
            FECHA_INICIO,
        )
        por_producto = [(r.Codigo, r.Nombre, float(r.Unidades or 0), float(r.Monto or 0)) for r in cur.fetchall()]

        return {
            "facturas": total.Facturas or 0,
            "unidades": float(total.Unidades or 0),
            "monto": float(total.Monto or 0),
            "por_mes": por_mes,
            "por_producto": por_producto,
        }
    finally:
        conn.close()


def _resumen_actual(codigos):
    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos)

        # Total viene en la moneda del documento (CurrencyID); multiplicar por
        # Rate lo convierte siempre a pesos (para documentos en pesos el tipo
        # de cambio ya está guardado como 1.0).
        cur.execute(
            """
            SELECT COUNT(DISTINCT d.DocumentID) Facturas, SUM(di.Quantity) Unidades,
                   SUM(di.Total * d.Rate) Monto
            FROM docDocumentItem di
            JOIN docDocument d ON d.DocumentID = di.DocumentID
            JOIN #Filtros f ON f.Codigo = di.ProductKey
            WHERE d.ModuleID = ? AND d.DocumentTypeID = ?
              AND d.CancelledOn IS NULL
              AND d.DateDocument >= ?
        """,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            FECHA_INICIO,
        )
        total = cur.fetchone()

        cur.execute(
            """
            SELECT FORMAT(d.DateDocument, 'yyyy-MM') Mes, SUM(di.Quantity) Unidades,
                   SUM(di.Total * d.Rate) Monto
            FROM docDocumentItem di
            JOIN docDocument d ON d.DocumentID = di.DocumentID
            JOIN #Filtros f ON f.Codigo = di.ProductKey
            WHERE d.ModuleID = ? AND d.DocumentTypeID = ?
              AND d.CancelledOn IS NULL
              AND d.DateDocument >= ?
            GROUP BY FORMAT(d.DateDocument, 'yyyy-MM')
        """,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            FECHA_INICIO,
        )
        por_mes = [(r.Mes, float(r.Unidades or 0), float(r.Monto or 0)) for r in cur.fetchall()]

        cur.execute(
            """
            SELECT f.Codigo, MAX(p.ProductName) Nombre,
                   SUM(di.Quantity) Unidades, SUM(di.Total * d.Rate) Monto
            FROM docDocumentItem di
            JOIN docDocument d ON d.DocumentID = di.DocumentID
            JOIN orgProduct p ON p.ProductID = di.ProductID
            JOIN #Filtros f ON f.Codigo = di.ProductKey
            WHERE d.ModuleID = ? AND d.DocumentTypeID = ?
              AND d.CancelledOn IS NULL
              AND d.DateDocument >= ?
            GROUP BY f.Codigo
        """,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            FECHA_INICIO,
        )
        por_producto = [(r.Codigo, r.Nombre, float(r.Unidades or 0), float(r.Monto or 0)) for r in cur.fetchall()]

        return {
            "facturas": total.Facturas or 0,
            "unidades": float(total.Unidades or 0),
            "monto": float(total.Monto or 0),
            "por_mes": por_mes,
            "por_producto": por_producto,
        }
    finally:
        conn.close()


def _combinar_series(mes_legacy, mes_actual):
    combinado = {}
    for mes, unidades, monto in mes_legacy + mes_actual:
        acc = combinado.setdefault(mes, {"mes": mes, "unidades": 0.0, "monto": 0.0})
        acc["unidades"] += unidades
        acc["monto"] += monto
    return [combinado[m] for m in sorted(combinado)]


def _combinar_productos(prod_legacy, prod_actual):
    combinado = {}
    for codigo, nombre, unidades, monto in prod_legacy + prod_actual:
        acc = combinado.setdefault(codigo, {"codigo": codigo, "nombre": nombre, "unidades": 0.0, "monto": 0.0})
        acc["unidades"] += unidades
        acc["monto"] += monto
        if not acc["nombre"] and nombre:
            acc["nombre"] = nombre
    filas = list(combinado.values())
    filas.sort(key=lambda r: r["unidades"], reverse=True)
    return filas


def resumen_combinado(codigos):
    legacy = _resumen_legacy(codigos)
    actual = _resumen_actual(codigos)

    return {
        "actualizado": date.today().isoformat(),
        "desde": FECHA_INICIO,
        "total": {
            "facturas": legacy["facturas"] + actual["facturas"],
            "unidades": legacy["unidades"] + actual["unidades"],
            "monto": legacy["monto"] + actual["monto"],
        },
        "por_mes": _combinar_series(legacy["por_mes"], actual["por_mes"]),
        "por_producto": _combinar_productos(legacy["por_producto"], actual["por_producto"]),
        "fuentes": {
            "legacy": {"facturas": legacy["facturas"], "unidades": legacy["unidades"]},
            "actual": {"facturas": actual["facturas"], "unidades": actual["unidades"]},
        },
    }


def _eventos_producto_legacy(codigo):
    conn = conectar(LEGACY_DB)
    try:
        cur = conn.cursor()
        placeholders = ",".join(str(x) for x in LEGACY_CONCEPTOS_FACTURA)
        cur.execute(
            f"""
            SELECT d.CFECHA Fecha, d.CIDCLIENTEPROVEEDOR ClienteId, d.CRAZONSOCIAL Cliente,
                   m.CUNIDADES Unidades, m.CTOTAL Monto, mon.CCLAVESAT Moneda
            FROM admMovimientos m
            JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
            JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
            JOIN admMonedas mon ON mon.CIDMONEDA = d.CIDMONEDA
            WHERE RTRIM(p.CCODIGOPRODUCTO) = ? COLLATE Modern_Spanish_CI_AS
              AND d.CIDCONCEPTODOCUMENTO IN ({placeholders})
              AND d.CCANCELADO = 0
              AND d.CFECHA >= ?
            ORDER BY d.CFECHA DESC
        """,
            codigo,
            FECHA_INICIO,
        )
        return [
            {
                "fecha": r.Fecha.isoformat(),
                "fuente": "legacy",
                "cliente_id": r.ClienteId,
                "cliente": r.Cliente,
                "unidades": float(r.Unidades or 0),
                "monto": float(r.Monto or 0),
                "moneda": r.Moneda,
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def _eventos_producto_actual(codigo):
    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT d.DateDocument Fecha, d.BusinessEntityID ClienteId,
                   COALESCE(NULLIF(be.CommercialName, ''), be.OfficialName) Cliente,
                   di.Quantity Unidades, di.Total Monto, mon.IntlSymbol Moneda
            FROM docDocumentItem di
            JOIN docDocument d ON d.DocumentID = di.DocumentID
            JOIN orgBusinessEntity be ON be.BusinessEntityID = d.BusinessEntityID
            JOIN engRefCurrency mon ON mon.CurrencyID = d.CurrencyID
            WHERE di.ProductKey = ?
              AND d.ModuleID = ? AND d.DocumentTypeID = ?
              AND d.CancelledOn IS NULL
              AND d.DateDocument >= ?
            ORDER BY d.DateDocument DESC
        """,
            codigo,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            FECHA_INICIO,
        )
        return [
            {
                "fecha": r.Fecha.isoformat(),
                "fuente": "actual",
                "cliente_id": r.ClienteId,
                "cliente": r.Cliente,
                "unidades": float(r.Unidades or 0),
                "monto": float(r.Monto or 0),
                "moneda": r.Moneda,
            }
            for r in cur.fetchall()
        ]
    finally:
        conn.close()


def timeline_producto(codigo):
    """Línea de tiempo de compras de un filtro, agrupada por cliente.

    El mismo cliente real puede existir en ambas bases con ids distintos
    (sistema histórico y sistema actual); se agrupa por nombre normalizado
    para mostrarlo como un solo cliente con una sola línea de tiempo.
    """
    eventos = _eventos_producto_legacy(codigo) + _eventos_producto_actual(codigo)
    vida_util_meses = negocio.get_vida_util(codigo)

    clientes = {}
    for ev in eventos:
        nombre_normalizado = normalizar_nombre(ev["cliente"])
        clave = nombre_normalizado or (ev["fuente"], ev["cliente_id"])
        acc = clientes.setdefault(
            clave,
            {
                "cliente": ev["cliente"],
                "clave_cliente": nombre_normalizado or None,
                "legacy_id": None,
                "actual_id": None,
                "unidades_total": 0.0,
                "compras": [],
            },
        )
        if ev["fuente"] == "legacy":
            acc["legacy_id"] = ev["cliente_id"]
        else:
            acc["actual_id"] = ev["cliente_id"]
        acc["unidades_total"] += ev["unidades"]
        acc["compras"].append(
            {
                "fecha": ev["fecha"],
                "unidades": ev["unidades"],
                "precio_unitario": ev["monto"] / ev["unidades"] if ev["unidades"] else 0,
                "monto": ev["monto"],
                "moneda": ev["moneda"],
            }
        )

    lista = list(clientes.values())
    for c in lista:
        c["compras"].sort(key=lambda x: x["fecha"], reverse=True)
        maquinas = negocio.get_maquinas(c["clave_cliente"], codigo) if c["clave_cliente"] else None
        c["maquinas"] = maquinas
        ultima = c["compras"][0]
        estado = negocio.resolver_estado(
            c["clave_cliente"], codigo, ultima["fecha"], ultima["unidades"], vida_util_meses, maquinas
        )
        ultima["proximo_contacto"] = estado["proximo_contacto"]
        c["estado"] = estado["estado"]
        c["nota_estado"] = estado["nota"]
        for compra in c["compras"][1:]:
            compra["proximo_contacto"] = None
    lista.sort(key=lambda c: c["compras"][0]["fecha"], reverse=True)

    return {
        "codigo": codigo,
        "unidades_total": sum(ev["unidades"] for ev in eventos),
        "vida_util_meses": vida_util_meses,
        "clientes": lista,
    }
