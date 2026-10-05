"""Catalogo de filtros vigilados, vida util por filtro y maquinas por cliente."""

from app.negocio.conexion import conectar


def listar_filtros():
    conn = conectar()
    try:
        return [r[0] for r in conn.execute("SELECT codigo FROM filtros").fetchall()]
    finally:
        conn.close()


def seed_filtros(codigos):
    """Inserta códigos solo si la tabla filtros está vacía (siembra inicial
    desde el Excel, una sola vez por máquina)."""
    conn = conectar()
    try:
        existentes = conn.execute("SELECT COUNT(*) FROM filtros").fetchone()[0]
        if existentes == 0:
            conn.executemany("INSERT OR IGNORE INTO filtros (codigo) VALUES (?)", [(c,) for c in codigos])
            conn.commit()
    finally:
        conn.close()


def agregar_filtro(codigo):
    conn = conectar()
    try:
        conn.execute("INSERT OR IGNORE INTO filtros (codigo) VALUES (?)", (codigo,))
        conn.commit()
    finally:
        conn.close()


def listar_vida_util():
    conn = conectar()
    try:
        return dict(conn.execute("SELECT codigo, meses FROM vida_util").fetchall())
    finally:
        conn.close()


def get_vida_util(codigo):
    conn = conectar()
    try:
        row = conn.execute("SELECT meses FROM vida_util WHERE codigo = ?", (codigo,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_vida_util(codigo, meses):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO vida_util (codigo, meses) VALUES (?, ?) "
            "ON CONFLICT(codigo) DO UPDATE SET meses = excluded.meses",
            (codigo, meses),
        )
        conn.commit()
    finally:
        conn.close()


def get_maquinas(clave_cliente, codigo):
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT cantidad FROM maquinas WHERE clave_cliente = ? AND codigo = ?",
            (clave_cliente, codigo),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def set_maquinas(clave_cliente, codigo, cantidad):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO maquinas (clave_cliente, codigo, cantidad) VALUES (?, ?, ?) "
            "ON CONFLICT(clave_cliente, codigo) DO UPDATE SET cantidad = excluded.cantidad",
            (clave_cliente, codigo, cantidad),
        )
        conn.commit()
    finally:
        conn.close()


def listar_maquinas():
    """Todas las filas de maquinas de una sola vez: {(clave_cliente, codigo): cantidad}."""
    conn = conectar()
    try:
        filas = conn.execute("SELECT clave_cliente, codigo, cantidad FROM maquinas").fetchall()
        return {(r[0], r[1]): r[2] for r in filas}
    finally:
        conn.close()
