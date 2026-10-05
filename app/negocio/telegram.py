"""Telegram en la base propia: avisos enviados, lo que el bot espera que le escriban, destinatarios e invitaciones."""

import secrets
from datetime import datetime

from app.negocio.conexion import conectar


def registrar_alerta_telegram(clave_cliente, codigo, chat_id, message_id, texto=None, prueba=False):
    conn = conectar()
    try:
        cur = conn.execute(
            "INSERT INTO alertas_telegram (clave_cliente, codigo, chat_id, message_id, creado_en, texto, prueba) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (clave_cliente, codigo, chat_id, message_id, datetime.now().isoformat(), texto, 1 if prueba else 0),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def dias_desde_ultimo_aviso(clave_cliente, codigo, chat_id):
    """Dias desde el ultimo aviso de ese cliente+filtro a ese chat (0 = hoy).
    None si nunca se le ha avisado."""
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT CAST(julianday(date('now', 'localtime')) - julianday(date(MAX(creado_en))) AS INTEGER) "
            "FROM alertas_telegram WHERE clave_cliente = ? AND codigo = ? AND chat_id = ?",
            (clave_cliente, codigo, chat_id),
        ).fetchone()
        return row[0]
    finally:
        conn.close()


def descartar_alerta_telegram(alerta_id):
    """Borra el registro de una alerta cuyo envio fallo, para poder reintentarla."""
    conn = conectar()
    try:
        conn.execute("DELETE FROM alertas_telegram WHERE id = ?", (alerta_id,))
        conn.commit()
    finally:
        conn.close()


def obtener_alerta_telegram(alerta_id):
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT id, clave_cliente, codigo, chat_id, message_id, creado_en, resuelto, texto "
            "FROM alertas_telegram WHERE id = ?",
            (alerta_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "clave_cliente": row[1],
            "codigo": row[2],
            "chat_id": row[3],
            "message_id": row[4],
            "creado_en": row[5],
            "resuelto": bool(row[6]),
            "texto": row[7],
        }
    finally:
        conn.close()


def guardar_texto_alerta(alerta_id, texto):
    conn = conectar()
    try:
        conn.execute("UPDATE alertas_telegram SET texto = ? WHERE id = ?", (texto, alerta_id))
        conn.commit()
    finally:
        conn.close()


def actualizar_message_id(alerta_id, message_id):
    conn = conectar()
    try:
        conn.execute("UPDATE alertas_telegram SET message_id = ? WHERE id = ?", (message_id, alerta_id))
        conn.commit()
    finally:
        conn.close()


def marcar_alerta_resuelta(alerta_id):
    conn = conectar()
    try:
        conn.execute("UPDATE alertas_telegram SET resuelto = 1 WHERE id = ?", (alerta_id,))
        conn.commit()
    finally:
        conn.close()


def set_espera(chat_id, alerta_id, tipo):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO telegram_espera (chat_id, alerta_id, tipo) VALUES (?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET alerta_id = excluded.alerta_id, tipo = excluded.tipo",
            (chat_id, alerta_id, tipo),
        )
        conn.commit()
    finally:
        conn.close()


def get_espera(chat_id):
    conn = conectar()
    try:
        row = conn.execute("SELECT alerta_id, tipo FROM telegram_espera WHERE chat_id = ?", (chat_id,)).fetchone()
        return {"alerta_id": row[0], "tipo": row[1]} if row else None
    finally:
        conn.close()


def limpiar_espera(chat_id):
    conn = conectar()
    try:
        conn.execute("DELETE FROM telegram_espera WHERE chat_id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()


def crear_invitacion_telegram(nombre, usuario_id=None):
    token = secrets.token_urlsafe(8)
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO telegram_invitaciones (token, usuario_id, nombre, creado_en) VALUES (?, ?, ?, ?)",
            (token, usuario_id, nombre, datetime.now().isoformat()),
        )
        conn.commit()
        return token
    finally:
        conn.close()


def resolver_invitacion(token):
    conn = conectar()
    try:
        row = conn.execute(
            "SELECT usuario_id, nombre, usado_en FROM telegram_invitaciones WHERE token = ?", (token,)
        ).fetchone()
        return {"usuario_id": row[0], "nombre": row[1], "usado_en": row[2]} if row else None
    finally:
        conn.close()


def marcar_invitacion_usada(token):
    conn = conectar()
    try:
        conn.execute(
            "UPDATE telegram_invitaciones SET usado_en = ? WHERE token = ?",
            (datetime.now().isoformat(), token),
        )
        conn.commit()
    finally:
        conn.close()


def agregar_chat_telegram(chat_id, nombre, usuario_id=None):
    conn = conectar()
    try:
        conn.execute(
            "INSERT INTO telegram_chats (chat_id, usuario_id, nombre, agregado_en) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(chat_id) DO UPDATE SET nombre = excluded.nombre, usuario_id = excluded.usuario_id",
            (chat_id, usuario_id, nombre, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def listar_chats_telegram():
    conn = conectar()
    try:
        filas = conn.execute("SELECT chat_id, usuario_id, nombre, agregado_en FROM telegram_chats").fetchall()
        return [{"chat_id": r[0], "usuario_id": r[1], "nombre": r[2], "agregado_en": r[3]} for r in filas]
    finally:
        conn.close()


def quitar_chat_telegram(chat_id):
    conn = conectar()
    try:
        conn.execute("DELETE FROM telegram_chats WHERE chat_id = ?", (chat_id,))
        conn.commit()
    finally:
        conn.close()
