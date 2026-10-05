"""Seguimientos: cada contacto con un cliente sobre un filtro (resultado, fecha, nota, quien)."""

from datetime import date, datetime, timedelta

from app.negocio.conexion import conectar


def registrar_seguimiento(clave_cliente, codigo, resultado, proximo_recordatorio, nota, usuario):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO seguimientos (clave_cliente, codigo, fecha, resultado, proximo_recordatorio, nota, usuario) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clave_cliente, codigo, datetime.now().isoformat(), resultado, proximo_recordatorio, nota, usuario),
        )
        conn.commit()
    finally:
        conn.close()


def agregar_nota_ultimo_seguimiento(clave_cliente, codigo, texto):
    """Agrega `texto` a la nota del seguimiento mas reciente de ese cliente+filtro
    (se van sumando: "Llamé... · Mandé WhatsApp..."). Regresa la nota resultante."""
    conn = conectar()
    try:
        fila = conn.execute(
            "SELECT id, nota FROM seguimientos WHERE clave_cliente = ? AND codigo = ? ORDER BY id DESC LIMIT 1",
            (clave_cliente, codigo),
        ).fetchone()
        if not fila:
            return None
        nota = f"{fila[1]} · {texto}" if fila[1] else texto
        conn.execute("UPDATE seguimientos SET nota = ? WHERE id = ?", (nota, fila[0]))
        conn.commit()
        return nota
    finally:
        conn.close()


def historial_seguimiento(clave_cliente, codigo):
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT fecha, resultado, proximo_recordatorio, nota, usuario FROM seguimientos "
            "WHERE clave_cliente = ? AND codigo = ? ORDER BY fecha DESC",
            (clave_cliente, codigo),
        ).fetchall()
        return [
            {"fecha": r[0], "resultado": r[1], "proximo_recordatorio": r[2], "nota": r[3], "usuario": r[4]}
            for r in filas
        ]
    finally:
        conn.close()


def ultimo_seguimiento(clave_cliente, codigo):
    historial = historial_seguimiento(clave_cliente, codigo)
    return historial[0] if historial else None


def listar_seguimientos(dias=None):
    """Todos los seguimientos de los ultimos `dias` dias (None = todo), del mas reciente al mas antiguo."""
    desde = (date.today() - timedelta(days=dias)).isoformat() if dias else "0000-00-00"
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT fecha, clave_cliente, codigo, resultado, proximo_recordatorio, nota "
            "FROM seguimientos WHERE fecha >= ? ORDER BY fecha DESC",
            (desde,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {"fecha": f, "clave_cliente": c, "codigo": k, "resultado": r, "proximo_recordatorio": pr, "nota": n}
        for f, c, k, r, pr, n in filas
    ]
