"""Clientes: busqueda por nombre y linea de tiempo de compras de un cliente (todos sus filtros)."""

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


def buscar_clientes(texto, codigos, limite=15):
    """Clientes que compraron filtros, filtrados por nombre.

    Combina ambas bases en un solo resultado por cliente real (emparejado
    por nombre normalizado), cargando el/los id(s) de cada fuente donde
    exista para poder traer su línea de tiempo completa después.
    """
    patron = f"%{texto}%"
    crudos = []

    conn = conectar(LEGACY_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos, collate="Modern_Spanish_CI_AS")
        placeholders = ",".join(str(x) for x in LEGACY_CONCEPTOS_FACTURA)
        cur.execute(
            f"""
            SELECT DISTINCT TOP {limite} d.CIDCLIENTEPROVEEDOR Id, d.CRAZONSOCIAL Nombre
            FROM admDocumentos d
            JOIN admMovimientos m ON m.CIDDOCUMENTO = d.CIDDOCUMENTO
            JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
            JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
            WHERE d.CIDCONCEPTODOCUMENTO IN ({placeholders})
              AND d.CCANCELADO = 0
              AND d.CRAZONSOCIAL LIKE ?
        """,
            patron,
        )
        crudos += [{"fuente": "legacy", "id": r.Id, "nombre": r.Nombre} for r in cur.fetchall()]
    finally:
        conn.close()

    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos)
        cur.execute(
            f"""
            SELECT DISTINCT TOP {limite} be.BusinessEntityID Id,
                   COALESCE(NULLIF(be.CommercialName, ''), be.OfficialName) Nombre
            FROM docDocument d
            JOIN docDocumentItem di ON di.DocumentID = d.DocumentID
            JOIN orgBusinessEntity be ON be.BusinessEntityID = d.BusinessEntityID
            JOIN #Filtros f ON f.Codigo = di.ProductKey
            WHERE d.ModuleID = ? AND d.DocumentTypeID = ? AND d.CancelledOn IS NULL
              AND (be.CommercialName LIKE ? OR be.OfficialName LIKE ?)
        """,
            ACTUAL_MODULE_ID,
            ACTUAL_DOCUMENT_TYPE_ID,
            patron,
            patron,
        )
        crudos += [{"fuente": "actual", "id": r.Id, "nombre": r.Nombre} for r in cur.fetchall()]
    finally:
        conn.close()

    combinados = {}
    for r in crudos:
        clave = normalizar_nombre(r["nombre"])
        acc = combinados.setdefault(clave, {"nombre": r["nombre"], "legacy_id": None, "actual_id": None})
        if r["fuente"] == "legacy":
            acc["legacy_id"] = r["id"]
        else:
            acc["actual_id"] = r["id"]

    return list(combinados.values())[:limite]


def timeline_cliente(codigos, legacy_id=None, actual_id=None):
    """Línea de tiempo de compras de filtros de un cliente, agrupada por
    producto, combinando ambas bases cuando el cliente existe en las dos."""
    eventos = []
    nombre_cliente = None

    if legacy_id is not None:
        conn = conectar(LEGACY_DB)
        try:
            cur = conn.cursor()
            temp_codigos(cur, codigos, collate="Modern_Spanish_CI_AS")
            placeholders = ",".join(str(x) for x in LEGACY_CONCEPTOS_FACTURA)
            cur.execute(
                f"""
                SELECT d.CFECHA Fecha, f.Codigo, MAX(RTRIM(p.CNOMBREPRODUCTO)) Nombre,
                       m.CUNIDADES Unidades, m.CTOTAL Monto, MAX(d.CRAZONSOCIAL) Cliente,
                       MAX(mon.CCLAVESAT) Moneda
                FROM admMovimientos m
                JOIN admDocumentos d ON d.CIDDOCUMENTO = m.CIDDOCUMENTO
                JOIN admProductos p ON p.CIDPRODUCTO = m.CIDPRODUCTO
                JOIN admMonedas mon ON mon.CIDMONEDA = d.CIDMONEDA
                JOIN #Filtros f ON f.Codigo = RTRIM(p.CCODIGOPRODUCTO)
                WHERE d.CIDCLIENTEPROVEEDOR = ?
                  AND d.CIDCONCEPTODOCUMENTO IN ({placeholders})
                  AND d.CCANCELADO = 0
                  AND d.CFECHA >= ?
                GROUP BY d.CFECHA, f.Codigo, m.CUNIDADES, m.CTOTAL, m.CIDMOVIMIENTO
                ORDER BY d.CFECHA DESC
            """,
                legacy_id,
                FECHA_INICIO,
            )
            filas = cur.fetchall()
            eventos += [
                {
                    "fecha": r.Fecha.isoformat(),
                    "codigo": r.Codigo,
                    "nombre": r.Nombre,
                    "unidades": float(r.Unidades or 0),
                    "monto": float(r.Monto or 0),
                    "moneda": r.Moneda,
                }
                for r in filas
            ]
            if filas:
                nombre_cliente = filas[0].Cliente
        finally:
            conn.close()

    if actual_id is not None:
        conn = conectar(ACTUAL_DB)
        try:
            cur = conn.cursor()
            temp_codigos(cur, codigos)
            cur.execute(
                """
                SELECT d.DateDocument Fecha, f.Codigo, MAX(p.ProductName) Nombre,
                       di.Quantity Unidades, di.Total Monto,
                       MAX(COALESCE(NULLIF(be.CommercialName, ''), be.OfficialName)) Cliente,
                       MAX(mon.IntlSymbol) Moneda
                FROM docDocumentItem di
                JOIN docDocument d ON d.DocumentID = di.DocumentID
                JOIN orgProduct p ON p.ProductID = di.ProductID
                JOIN orgBusinessEntity be ON be.BusinessEntityID = d.BusinessEntityID
                JOIN engRefCurrency mon ON mon.CurrencyID = d.CurrencyID
                JOIN #Filtros f ON f.Codigo = di.ProductKey
                WHERE d.BusinessEntityID = ?
                  AND d.ModuleID = ? AND d.DocumentTypeID = ?
                  AND d.CancelledOn IS NULL
                  AND d.DateDocument >= ?
                GROUP BY d.DateDocument, f.Codigo, di.Quantity, di.Total, di.DocumentItemID
                ORDER BY d.DateDocument DESC
            """,
                actual_id,
                ACTUAL_MODULE_ID,
                ACTUAL_DOCUMENT_TYPE_ID,
                FECHA_INICIO,
            )
            filas = cur.fetchall()
            eventos += [
                {
                    "fecha": r.Fecha.isoformat(),
                    "codigo": r.Codigo,
                    "nombre": r.Nombre,
                    "unidades": float(r.Unidades or 0),
                    "monto": float(r.Monto or 0),
                    "moneda": r.Moneda,
                }
                for r in filas
            ]
            if filas and not nombre_cliente:
                nombre_cliente = filas[0].Cliente
        finally:
            conn.close()

    clave_cliente = normalizar_nombre(nombre_cliente) or None

    productos = {}
    for ev in eventos:
        acc = productos.setdefault(
            ev["codigo"],
            {
                "codigo": ev["codigo"],
                "nombre": ev["nombre"],
                "unidades_total": 0.0,
                "compras": [],
            },
        )
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

    lista = list(productos.values())
    for p in lista:
        p["compras"].sort(key=lambda x: x["fecha"], reverse=True)
        p["vida_util_meses"] = negocio.get_vida_util(p["codigo"])
        p["maquinas"] = negocio.get_maquinas(clave_cliente, p["codigo"]) if clave_cliente else None
        ultima = p["compras"][0]
        estado = negocio.resolver_estado(
            clave_cliente, p["codigo"], ultima["fecha"], ultima["unidades"], p["vida_util_meses"], p["maquinas"]
        )
        ultima["proximo_contacto"] = estado["proximo_contacto"]
        p["estado"] = estado["estado"]
        p["nota_estado"] = estado["nota"]
        for compra in p["compras"][1:]:
            compra["proximo_contacto"] = None
    lista.sort(key=lambda p: p["compras"][0]["fecha"], reverse=True)

    return {
        "cliente": nombre_cliente,
        "clave_cliente": clave_cliente,
        "productos": lista,
    }
