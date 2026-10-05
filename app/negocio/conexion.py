"""Conexion a la base propia (SQLite, config/negocio.db) y su esquema.

Las tablas se crean y se migran solas cada vez que se abre una conexion (conectar()).
"""

import sqlite3

from app.config import ruta_config

RUTA_DB = ruta_config("negocio.db")


def conectar():
    """Abre la base propia, creando las tablas y migrando las columnas que falten."""
    conn = sqlite3.connect(RUTA_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS vida_util (
            codigo TEXT PRIMARY KEY,
            meses REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS maquinas (
            clave_cliente TEXT NOT NULL,
            codigo TEXT NOT NULL,
            cantidad INTEGER NOT NULL,
            PRIMARY KEY (clave_cliente, codigo)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS filtros (
            codigo TEXT PRIMARY KEY
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            rol TEXT NOT NULL DEFAULT 'vendedor',
            creado_en TEXT NOT NULL
        )
    """)
    _migrar_usuarios(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seguimientos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave_cliente TEXT NOT NULL,
            codigo TEXT NOT NULL,
            fecha TEXT NOT NULL,
            resultado TEXT NOT NULL,
            proximo_recordatorio TEXT,
            nota TEXT,
            usuario TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alertas_telegram (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave_cliente TEXT NOT NULL,
            codigo TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            message_id INTEGER NOT NULL,
            creado_en TEXT NOT NULL,
            resuelto INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_espera (
            chat_id TEXT PRIMARY KEY,
            alerta_id INTEGER NOT NULL,
            tipo TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_chats (
            chat_id TEXT PRIMARY KEY,
            usuario_id INTEGER,
            nombre TEXT NOT NULL,
            agregado_en TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS telegram_invitaciones (
            token TEXT PRIMARY KEY,
            usuario_id INTEGER,
            nombre TEXT NOT NULL,
            creado_en TEXT NOT NULL,
            usado_en TEXT
        )
    """)
    _migrar_telegram_usuario_id(conn)
    _migrar_alertas_texto(conn)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS intentos_login (
            username TEXT PRIMARY KEY,
            intentos INTEGER NOT NULL DEFAULT 0,
            bloqueado_hasta TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS historial_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            codigo TEXT NOT NULL,
            clave_cliente TEXT,
            valor REAL NOT NULL,
            usuario TEXT,
            fecha TEXT NOT NULL
        )
    """)
    return conn


def _migrar_usuarios(conn):
    """Cuentas creadas con el esquema viejo (columna email, sin rol) se
    adaptan al nuevo esquema (username, rol) sin perder datos. El primer
    usuario existente (el original) queda como admin."""
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(usuarios)").fetchall()}
    if "email" in columnas and "username" not in columnas:
        conn.execute("ALTER TABLE usuarios RENAME COLUMN email TO username")
        columnas.discard("email")
        columnas.add("username")
    if "rol" not in columnas:
        conn.execute("ALTER TABLE usuarios ADD COLUMN rol TEXT NOT NULL DEFAULT 'admin'")
    conn.commit()


def _migrar_alertas_texto(conn):
    """Guarda el texto (HTML) de cada aviso enviado, para poder conservarlo
    cuando el mensaje se edita al registrar el seguimiento desde Telegram."""
    columnas = {r[1] for r in conn.execute("PRAGMA table_info(alertas_telegram)").fetchall()}
    if "texto" not in columnas:
        conn.execute("ALTER TABLE alertas_telegram ADD COLUMN texto TEXT")
        conn.commit()
    if "prueba" not in columnas:
        conn.execute("ALTER TABLE alertas_telegram ADD COLUMN prueba INTEGER NOT NULL DEFAULT 0")
        conn.commit()


def _migrar_telegram_usuario_id(conn):
    """Las tablas de Telegram nacieron sin usuario_id (invitacion por nombre
    libre); se agrega para poder ligar el chat a una cuenta real."""
    for tabla in ("telegram_chats", "telegram_invitaciones"):
        columnas = {r[1] for r in conn.execute(f"PRAGMA table_info({tabla})").fetchall()}
        if "usuario_id" not in columnas:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN usuario_id INTEGER")
    conn.commit()
