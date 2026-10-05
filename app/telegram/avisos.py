"""Envio de avisos de recontacto por Telegram (un mensaje por cliente+filtro,
con botones para registrar el seguimiento). Lo usan el resumen diario
(telegram_alertas.py) y el servidor web (aviso inmediato al capturar vida
util o maquinas)."""

import html
import json

import requests

from app import negocio
from app.config import ruta_config
from app.erp import alertas_recontacto

RUTA_CONFIG = ruta_config("telegram_config.json")

# Tope de mensajes por captura: cambiar la vida util de un filtro con muchos
# clientes vencidos no debe inundar el chat; el resto sale en el resumen diario.
MAX_AVISO_INMEDIATO = 15


def cargar_config():
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    if "chat_ids" not in cfg and "chat_id" in cfg:
        cfg["chat_ids"] = [cfg["chat_id"]]
    return cfg


def destinatarios(cfg):
    """Chats fijos de telegram_config.json mas los dados de alta por link de
    invitacion (tabla telegram_chats), sin repetir."""
    fijos = list(cfg.get("chat_ids", []))
    invitados = [c["chat_id"] for c in negocio.listar_chats_telegram()]
    vistos = set()
    resultado = []
    for cid in fijos + invitados:
        cid = str(cid)
        if cid not in vistos:
            vistos.add(cid)
            resultado.append(cid)
    return resultado


def _teclado(alerta_id):
    return {
        "inline_keyboard": [
            [
                {"text": "Pidió esperar", "callback_data": f"esperar|{alerta_id}"},
                {"text": "Volvió a comprar", "callback_data": f"vendio|{alerta_id}"},
            ],
            [
                {"text": "Cambió de proveedor", "callback_data": f"proveedor|{alerta_id}"},
                {"text": "No contestó", "callback_data": f"no_contesto|{alerta_id}"},
            ],
            [
                {"text": "No aplica (descartar)", "callback_data": f"no_aplica|{alerta_id}"},
            ],
        ]
    }


def _texto(a):
    icono = "\U0001f534" if a["vencido"] else "\U0001f7e0"
    estado = "venció" if a["vencido"] else "vence"
    # Los nombres pueden traer & o < (p. ej. "A & B S.A."), que romperian el HTML de Telegram.
    texto = (
        f"{icono} <b>{html.escape(a['cliente'] or '')}</b>\n"
        f"   {html.escape(a['codigo'])} — {html.escape(a['nombre_producto'] or '')}\n"
        f"   {estado} {a['proximo_contacto']}"
    )
    if a.get("estado") == "factura_vencida":
        texto += (
            f"\n   \U0001f9fe Dijeron que volvió a comprar el {a['nota_estado']}, pero sigue sin factura: contáctalo"
        )
    return texto


def enviar_mensaje(token, chat_id, texto, teclado=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": texto, "parse_mode": "HTML"}
    if teclado:
        payload["reply_markup"] = teclado
    r = requests.post(url, json=payload, timeout=15)
    r.raise_for_status()
    return r.json()["result"]


def _ya_avisado(alerta, chat_id, dias_entre_avisos):
    d = negocio.dias_desde_ultimo_aviso(alerta["clave_cliente"], alerta["codigo"], chat_id)
    return d is not None and d < dias_entre_avisos


def enviar_alertas(cfg, chats, alertas, maximo=None, dias_entre_avisos=1):
    """Manda cada alerta a cada chat, salvo que ya se le haya avisado hace
    menos de `dias_entre_avisos` dias (1 = no repetir el mismo dia).
    Con `maximo`, solo las primeras N alertas; el resto se avisa en un
    mensaje final. Regresa (alertas_enviadas, alertas_omitidas)."""
    enviadas = 0
    omitidas = 0
    for a in alertas:
        pendientes = [c for c in chats if not _ya_avisado(a, c, dias_entre_avisos)]
        if not pendientes:
            continue
        if maximo is not None and enviadas >= maximo:
            omitidas += 1
            continue
        algun_envio = False
        texto = _texto(a)
        for chat_id in pendientes:
            alerta_id = negocio.registrar_alerta_telegram(a["clave_cliente"], a["codigo"], chat_id, 0, texto)
            try:
                resultado = enviar_mensaje(cfg["token"], chat_id, texto, _teclado(alerta_id))
            except requests.RequestException:
                negocio.descartar_alerta_telegram(alerta_id)
                continue
            negocio.actualizar_message_id(alerta_id, resultado["message_id"])
            algun_envio = True
        if algun_envio:
            enviadas += 1

    if omitidas:
        aviso = f"ℹ️ Y {omitidas} aviso(s) más. El resto llegará en el resumen diario de las 8:30 am."
        for chat_id in chats:
            try:
                enviar_mensaje(cfg["token"], chat_id, aviso)
            except requests.RequestException:
                pass
    return enviadas, omitidas


def avisar_alertas(codigo, clave_cliente=None):
    """Aviso inmediato: revisa solo el filtro `codigo` (y, si se da, solo ese
    cliente) y manda lo que este vencido o por vencer en 7 dias."""
    cfg = cargar_config()
    chats = destinatarios(cfg)
    if not chats:
        return 0, 0
    alertas = alertas_recontacto([codigo])
    if clave_cliente:
        alertas = [a for a in alertas if a["clave_cliente"] == clave_cliente]
    return enviar_alertas(cfg, chats, alertas, maximo=MAX_AVISO_INMEDIATO)
