"""Usuarios de la pagina: alta, verificacion y cambio de contrasena.

Las contrasenas se guardan con hash. Toda contrasena nueva pasa por validar_password (minimo 10
caracteres, no solo numeros, no repetitiva, distinta del usuario), venga de la pagina o de
crear_usuario.py. El bloqueo por intentos fallidos vive en negocio.py.
"""

from datetime import datetime

from werkzeug.security import check_password_hash, generate_password_hash

from app.negocio.conexion import conectar

MIN_PASSWORD = 10
REGLAS_PASSWORD = f"Mínimo {MIN_PASSWORD} caracteres, que no sean solo números y distinta del usuario."


def validar_password(password, username=None):
    """Regresa el motivo por el que la contraseña no sirve, o None si cumple el minimo."""
    if len(password or "") < MIN_PASSWORD:
        return f"la contraseña debe tener al menos {MIN_PASSWORD} caracteres"
    if password.isdigit():
        return "la contraseña no puede ser solo números"
    if len(set(password)) < 4:
        return "la contraseña es demasiado repetitiva"
    if username and password.strip().lower() == username.strip().lower():
        return "la contraseña no puede ser igual al usuario"
    return None


def _exigir_password_valida(password, username):
    motivo = validar_password(password, username)
    if motivo:
        raise ValueError(motivo)


def crear_usuario(nombre, username, password, rol="vendedor"):
    _exigir_password_valida(password, username)
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO usuarios (nombre, username, password_hash, rol, creado_en) VALUES (?, ?, ?, ?, ?)",
            (nombre, username.strip().lower(), generate_password_hash(password), rol, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def verificar_usuario(username, password):
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT id, nombre, username, password_hash, rol FROM usuarios WHERE username = ?",
            (username.strip().lower(),),
        ).fetchone()
        if row and check_password_hash(row[3], password):
            return {"id": row[0], "nombre": row[1], "username": row[2], "rol": row[4]}
        return None
    finally:
        conn.close()


def establecer_password(username, password_nueva):
    """Cambia la contraseña de cualquier usuario sin pedir la anterior.
    Solo debe llamarse desde una ruta protegida para administradores."""
    _exigir_password_valida(password_nueva, username)
    conn = conectar()
    try:
        cur = conn.execute(
            "UPDATE usuarios SET password_hash = ? WHERE username = ?",
            (generate_password_hash(password_nueva), username.strip().lower()),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def cambiar_password(username, password_actual, password_nueva):
    """Regresa True si se cambio, False si la contraseña actual no coincide."""
    if not verificar_usuario(username, password_actual):
        return False
    _exigir_password_valida(password_nueva, username)
    conn = conectar()
    try:
        conn.execute(
            "UPDATE usuarios SET password_hash = ? WHERE username = ?",
            (generate_password_hash(password_nueva), username.strip().lower()),
        )
        conn.commit()
        return True
    finally:
        conn.close()


def listar_usuarios():
    conn = conectar()
    try:
        filas = conn.execute("SELECT id, nombre, username, rol, creado_en FROM usuarios ORDER BY creado_en").fetchall()
        return [{"id": r[0], "nombre": r[1], "username": r[2], "rol": r[3], "creado_en": r[4]} for r in filas]
    finally:
        conn.close()


def existe_algun_usuario():
    conn = conectar()
    try:
        return conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] > 0
    finally:
        conn.close()
