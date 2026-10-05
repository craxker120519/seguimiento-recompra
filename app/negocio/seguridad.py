"""Bloqueo de login por intentos fallidos y bitacora de cambios de vida util y maquinas."""

from datetime import datetime, timedelta

from app.negocio.conexion import conectar

_MAX_INTENTOS_LOGIN = 5
_BLOQUEO_MINUTOS = 15


def esta_bloqueado(username):
    """Regresa los minutos restantes de bloqueo (int > 0) o None si puede intentar."""
    username = username.strip().lower()
    conn = conectar()
    try:
        row = conn.execute("SELECT bloqueado_hasta FROM intentos_login WHERE username = ?", (username,)).fetchone()
        if not row or not row[0]:
            return None
        restante = datetime.fromisoformat(row[0]) - datetime.now()
        if restante.total_seconds() <= 0:
            return None
        return max(1, int(restante.total_seconds() // 60) + 1)
    finally:
        conn.close()


def registrar_intento_fallido(username):
    username = username.strip().lower()
    conn = conectar()
    try:
        row = conn.execute("SELECT intentos FROM intentos_login WHERE username = ?", (username,)).fetchone()
        intentos = (row[0] if row else 0) + 1
        bloqueado_hasta = None
        if intentos >= _MAX_INTENTOS_LOGIN:
            bloqueado_hasta = (datetime.now() + timedelta(minutes=_BLOQUEO_MINUTOS)).isoformat()
            intentos = 0
        conn.execute(
            "INSERT INTO intentos_login (username, intentos, bloqueado_hasta) VALUES (?, ?, ?) "
            "ON CONFLICT(username) DO UPDATE SET intentos = excluded.intentos, bloqueado_hasta = excluded.bloqueado_hasta",
            (username, intentos, bloqueado_hasta),
        )
        conn.commit()
    finally:
        conn.close()


def limpiar_intentos(username):
    username = username.strip().lower()
    conn = conectar()
    try:
        conn.execute("DELETE FROM intentos_login WHERE username = ?", (username,))
        conn.commit()
    finally:
        conn.close()


def registrar_cambio_config(tipo, codigo, clave_cliente, valor, usuario):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO historial_config (tipo, codigo, clave_cliente, valor, usuario, fecha) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (tipo, codigo, clave_cliente, valor, usuario, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def historial_config(limite=50):
    conn = conectar()
    try:
        filas = conn.execute(
            "SELECT tipo, codigo, clave_cliente, valor, usuario, fecha FROM historial_config "
            "ORDER BY fecha DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [
            {"tipo": r[0], "codigo": r[1], "clave_cliente": r[2], "valor": r[3], "usuario": r[4], "fecha": r[5]}
            for r in filas
        ]
    finally:
        conn.close()
