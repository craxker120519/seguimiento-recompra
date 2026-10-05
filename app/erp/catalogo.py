"""Catalogo de filtros en ERP: codigo y nombre de cada filtro, y busqueda para agregar uno nuevo."""

from app import negocio
from app.erp.conexion import ACTUAL_DB, conectar, temp_codigos


def catalogo_filtros(codigos, con_vida_util=False):
    """Código + nombre de cada filtro, para el autocomplete del buscador y
    para la pestaña de catálogo (con_vida_util=True agrega vida_util_meses)."""
    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        temp_codigos(cur, codigos)
        cur.execute("""
            SELECT f.Codigo, MAX(p.ProductName) Nombre
            FROM #Filtros f
            LEFT JOIN orgProduct p ON p.ProductKey = f.Codigo
            GROUP BY f.Codigo
        """)
        filas = [{"codigo": r.Codigo, "nombre": r.Nombre or r.Codigo} for r in cur.fetchall()]
    finally:
        conn.close()

    if con_vida_util:
        vida_util = negocio.listar_vida_util()
        for f in filas:
            f["vida_util_meses"] = vida_util.get(f["codigo"])
        filas.sort(key=lambda f: f["nombre"])

    return filas


def buscar_catalogo_erp(texto, codigos_ya_trackeados, limite=20):
    """Busca en el catálogo completo de productos de ERP (no solo los
    filtros ya trackeados), para poder dar de alta uno nuevo."""
    patron = f"%{texto}%"
    conn = conectar(ACTUAL_DB)
    try:
        cur = conn.cursor()
        cur.execute(
            f"""
            SELECT TOP {limite * 3} ProductKey, ProductName
            FROM orgProduct
            WHERE ProductKey LIKE ? OR ProductName LIKE ?
            ORDER BY ProductName
        """,
            patron,
            patron,
        )
        ya_trackeados = set(codigos_ya_trackeados)
        resultados = []
        for r in cur.fetchall():
            if r.ProductKey in ya_trackeados:
                continue
            resultados.append({"codigo": r.ProductKey, "nombre": r.ProductName})
            if len(resultados) >= limite:
                break
        return resultados
    finally:
        conn.close()
