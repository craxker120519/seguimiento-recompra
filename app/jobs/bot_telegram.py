"""Escucha respuestas de Telegram (botones y texto) para registrar el
seguimiento de recontacto directo desde el chat, sin entrar a la página web.

Pensado para quedar corriendo siempre en esta PC (long polling, sin
necesidad de servidor público ni webhook). Usa la misma función
app.negocio.registrar_seguimiento que ya usa la página — el bot es solo
otra puerta de entrada a los mismos datos.

Uso: python telegram_bot_escuchar.py
"""

import html
import json
import os
import time
from datetime import date, datetime, timedelta

import requests

from app import negocio
from app.config import ruta_config
from app.erp import alertas_recontacto, buscar_clientes, timeline_cliente
from app.negocio.filtros import codigos_filtro
from app.telegram import avisos, resumen

RUTA_CONFIG = ruta_config("telegram_config.json")
RUTA_OFFSET = ruta_config("telegram_offset.txt")

_TEXTOS_RESULTADO = {
    "vendio_de_nuevo": "Volvió a comprar",
    "no_contesto": "No contestó",
    "contactado_esperar": "Pidió esperar",
    "cambio_proveedor": "Cambió de proveedor",
    "no_aplica": "No aplica",
}


def _cfg():
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        cfg = json.load(f)
    if "chat_ids" not in cfg and "chat_id" in cfg:
        cfg["chat_ids"] = [cfg["chat_id"]]
    return cfg


def _leer_offset():
    if os.path.exists(RUTA_OFFSET):
        with open(RUTA_OFFSET, encoding="utf-8") as f:
            texto = f.read().strip()
            return int(texto) if texto else 0
    return 0


def _guardar_offset(offset):
    with open(RUTA_OFFSET, "w", encoding="utf-8") as f:
        f.write(str(offset))


def _api(token, metodo, payload):
    url = f"https://api.telegram.org/bot{token}/{metodo}"
    r = requests.post(url, json=payload, timeout=40)
    r.raise_for_status()
    return r.json().get("result")


def _editar_mensaje(token, chat_id, message_id, texto, teclado=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": texto, "parse_mode": "HTML"}
    if teclado is not None:
        payload["reply_markup"] = teclado
    try:
        _api(token, "editMessageText", payload)
    except requests.HTTPError:
        pass


def _responder_callback(token, callback_query_id, texto=None):
    payload = {"callback_query_id": callback_query_id}
    if texto:
        payload["text"] = texto
    _api(token, "answerCallbackQuery", payload)


def _mandar_mensaje(token, chat_id, texto, teclado=None):
    payload = {"chat_id": chat_id, "text": texto[:4000], "parse_mode": "HTML"}  # Telegram acepta hasta 4096
    if teclado:
        payload["reply_markup"] = teclado
    _api(token, "sendMessage", payload)


# ---- consultas: /hoy y /cliente (solo para los chats dados de alta) ----

AYUDA = (
    "Esto puedo hacer:\n"
    "/hoy — a quién toca contactar hoy y en los próximos 7 días\n"
    "/cliente nombre — el estado de cada filtro de un cliente (ej. /cliente kipp)\n\n"
    "Los avisos de recontacto traen botones para registrar el seguimiento."
)
_COMANDOS = [
    {"command": "hoy", "description": "A quién toca contactar hoy"},
    {"command": "cliente", "description": "Consultar un cliente: /cliente nombre"},
    {"command": "ayuda", "description": "Ver qué puedo hacer"},
]


def _autorizado(chat_id):
    """Solo los chats dados de alta (link de invitacion o telegram_config.json) pueden consultar datos."""
    try:
        return str(chat_id) in avisos.destinatarios(avisos.cargar_config())
    except Exception:
        return False


def _cmd_hoy(token, chat_id):
    try:
        todas = alertas_recontacto(codigos_filtro(), incluir_esperando_factura=True)
    except Exception:
        _mandar_mensaje(token, chat_id, "No pude consultar ERP en este momento. Intenta de nuevo en un minuto.")
        return
    contactar = [a for a in todas if a.get("estado") != "esperando_factura"]
    esperando = [a for a in todas if a.get("estado") == "esperando_factura"]
    texto = (
        resumen.texto_resumen(contactar, date.today()) or "✅ No hay nadie por contactar hoy ni en los próximos 7 días."
    )
    if esperando:
        texto += f"\n\n⏳ {len(esperando)} venta{'s' if len(esperando) != 1 else ''} registrada{'s' if len(esperando) != 1 else ''} esperando factura (aún dentro del plazo)."
    _mandar_mensaje(token, chat_id, texto)


def _ficha_cliente(token, chat_id, legacy_id, actual_id):
    try:
        datos = timeline_cliente(codigos_filtro(), legacy_id=legacy_id, actual_id=actual_id)
    except Exception:
        _mandar_mensaje(token, chat_id, "No pude consultar ERP en este momento. Intenta de nuevo en un minuto.")
        return
    if not datos["productos"]:
        _mandar_mensaje(token, chat_id, "Ese cliente no tiene compras de filtros registradas.")
        return
    _mandar_mensaje(token, chat_id, resumen.texto_cliente(datos, date.today(), maximo=15))


def _cmd_cliente(token, chat_id, consulta):
    if len(consulta) < 2:
        _mandar_mensaje(token, chat_id, "Escribe /cliente y parte del nombre, por ejemplo: /cliente kipp")
        return
    try:
        encontrados = buscar_clientes(consulta, codigos_filtro())
    except Exception:
        _mandar_mensaje(token, chat_id, "No pude consultar ERP en este momento. Intenta de nuevo en un minuto.")
        return
    if not encontrados:
        _mandar_mensaje(token, chat_id, f"No encontré ningún cliente con «{html.escape(consulta)}».")
        return
    if len(encontrados) == 1:
        _ficha_cliente(token, chat_id, encontrados[0]["legacy_id"], encontrados[0]["actual_id"])
        return
    botones = [
        [
            {
                "text": (c["nombre"] or "(sin nombre)")[:60],
                "callback_data": f"cli|{c['legacy_id'] or ''}|{c['actual_id'] or ''}",
            }
        ]
        for c in encontrados[:10]
    ]
    extra = " Muestro los primeros 10; escribe más letras para afinar." if len(encontrados) > 10 else ""
    _mandar_mensaje(
        token, chat_id, f"Encontré {len(encontrados)} clientes. Elige uno:{extra}", {"inline_keyboard": botones}
    )


def _callback_cliente(token, cq):
    chat_id = (cq.get("message") or {}).get("chat", {}).get("id")
    if not _autorizado(chat_id):
        _responder_callback(token, cq["id"], "Este chat no está autorizado.")
        return
    _, legacy, actual = (cq.get("data", "").split("|") + ["", ""])[:3]
    _responder_callback(token, cq["id"])
    _ficha_cliente(token, chat_id, int(legacy) if legacy.isdigit() else None, int(actual) if actual.isdigit() else None)


def _procesar_comando(token, chat_id, texto):
    """Regresa True si el texto era un comando (aunque no se pueda atender)."""
    comando, _, resto = texto.partition(" ")
    comando = comando.split("@")[0].lower()
    if comando not in ("/hoy", "/cliente", "/ayuda", "/help"):
        return False
    if not _autorizado(chat_id):
        _mandar_mensaje(
            token, chat_id, "Este chat no está dado de alta. Pide tu link de invitación para activar tus avisos."
        )
        return True
    if comando in ("/ayuda", "/help"):
        _mandar_mensaje(token, chat_id, AYUDA)
    elif comando == "/hoy":
        _cmd_hoy(token, chat_id)
    else:
        _cmd_cliente(token, chat_id, resto.strip())
    return True


def _cuerpo(alerta):
    """Texto original del aviso (cliente, filtro, fecha) para no perderlo al editar el mensaje."""
    if alerta.get("texto"):
        return alerta["texto"]
    return "<b>" + html.escape(alerta["clave_cliente"]) + "</b>\n   " + html.escape(alerta["codigo"])


def _quien(chat_id, remitente):
    """Nombre de la persona: el del usuario del sistema ligado a ese chat, o el de Telegram."""
    for c in negocio.listar_chats_telegram():
        if str(c["chat_id"]) == str(chat_id):
            return c["nombre"]
    return (remitente or {}).get("first_name") or "Telegram"


def _confirmar_y_cerrar(token, alerta, resultado, extra="", quien=None):
    negocio.marcar_alerta_resuelta(alerta["id"])
    hora = datetime.now().strftime("%d/%m %H:%M")
    firma = f"{html.escape(quien)}, {hora}" if quien else hora
    texto = (
        _cuerpo(alerta)
        + "\n\n✅ <b>Registrado: "
        + _TEXTOS_RESULTADO[resultado]
        + "</b>"
        + extra
        + "\n<i>"
        + firma
        + "</i>"
    )
    _editar_mensaje(token, alerta["chat_id"], alerta["message_id"], texto, teclado={"inline_keyboard": []})


_NOTAS_RAPIDAS = {
    "nc_llamada": "Llamé, sin respuesta",
    "nc_whatsapp": "Mandé WhatsApp, sin respuesta",
    "nc_correo": "Mandé correo, sin respuesta",
}


def _teclado_intentos(alerta_id):
    return {
        "inline_keyboard": [
            [
                {"text": "\U0001f4de Llamé", "callback_data": f"nc_llamada|{alerta_id}"},
                {"text": "\U0001f4ac WhatsApp", "callback_data": f"nc_whatsapp|{alerta_id}"},
                {"text": "✉️ Correo", "callback_data": f"nc_correo|{alerta_id}"},
            ],
            [
                {"text": "✍️ Escribir nota", "callback_data": f"nc_otra|{alerta_id}"},
                {"text": "Listo", "callback_data": f"nc_listo|{alerta_id}"},
            ],
        ]
    }


def _mostrar_no_contesto(token, alerta, pregunta=None, con_botones=True):
    """Muestra el aviso original + 'No contestó', el reintento programado y lo
    que se ha hecho para comunicarse (la nota), con botones para agregar mas."""
    seg = negocio.ultimo_seguimiento(alerta["clave_cliente"], alerta["codigo"])
    fecha = datetime.fromisoformat(seg["fecha"])
    reintento = (fecha.date() + timedelta(days=negocio.DIAS_REINTENTO)).strftime("%d/%m/%Y")
    texto = _cuerpo(alerta) + "\n\n✅ <b>Registrado: No contestó</b> · reintentar el " + reintento
    if seg.get("nota"):
        texto += "\n\U0001f4dd <b>Qué se hizo:</b> " + html.escape(seg["nota"])
    texto += "\n<i>" + html.escape(seg.get("usuario") or "") + ", " + fecha.strftime("%d/%m %H:%M") + "</i>"
    if pregunta:
        texto += "\n\n" + pregunta
    teclado = _teclado_intentos(alerta["id"]) if con_botones else {"inline_keyboard": []}
    _editar_mensaje(token, alerta["chat_id"], alerta["message_id"], texto, teclado=teclado)


def _pedir_dato(token, alerta, pregunta):
    """Deja visible el aviso y le agrega debajo lo que falta capturar."""
    _editar_mensaje(
        token,
        alerta["chat_id"],
        alerta["message_id"],
        _cuerpo(alerta) + "\n\n" + pregunta,
        teclado={"inline_keyboard": []},
    )


def _procesar_callback(token, cq):
    data = cq.get("data", "")
    if data.startswith("cli|"):
        _callback_cliente(token, cq)
        return
    if "|" not in data:
        return
    accion, alerta_id_texto = data.split("|", 1)
    try:
        alerta_id = int(alerta_id_texto)
    except ValueError:
        return

    alerta = negocio.obtener_alerta_telegram(alerta_id)
    if not alerta:
        _responder_callback(token, cq["id"], "Esta alerta ya no existe.")
        return
    es_nota_intento = accion.startswith("nc_")
    if alerta["resuelto"] and not es_nota_intento:
        _responder_callback(token, cq["id"], "Ya se había registrado.")
        return
    if es_nota_intento:
        ultimo = negocio.ultimo_seguimiento(alerta["clave_cliente"], alerta["codigo"])
        if not ultimo or ultimo["resultado"] != "no_contesto":
            _responder_callback(token, cq["id"], 'Ese aviso ya no está en "No contestó".')
            return

    chat_id = str(alerta["chat_id"])

    # Avisos enviados antes de guardar el texto: se toma del propio mensaje de Telegram.
    if not alerta.get("texto"):
        original = (cq.get("message") or {}).get("text")
        if original:
            alerta["texto"] = html.escape(original)
            negocio.guardar_texto_alerta(alerta_id, alerta["texto"])

    quien = _quien(chat_id, cq.get("from"))
    usuario = f"{quien} (Telegram)"

    if accion == "vendio":
        negocio.registrar_seguimiento(alerta["clave_cliente"], alerta["codigo"], "vendio_de_nuevo", None, None, usuario)
        _responder_callback(token, cq["id"])
        _confirmar_y_cerrar(token, alerta, "vendio_de_nuevo", quien=quien)
    elif accion == "no_contesto":
        negocio.registrar_seguimiento(alerta["clave_cliente"], alerta["codigo"], "no_contesto", None, None, usuario)
        negocio.marcar_alerta_resuelta(alerta_id)
        _responder_callback(token, cq["id"])
        _mostrar_no_contesto(
            token, alerta, pregunta="💬 ¿Qué hiciste para comunicarte? Toca una opción o escribe una nota."
        )
    elif accion in _NOTAS_RAPIDAS:
        negocio.agregar_nota_ultimo_seguimiento(alerta["clave_cliente"], alerta["codigo"], _NOTAS_RAPIDAS[accion])
        _responder_callback(token, cq["id"], "Anotado")
        _mostrar_no_contesto(token, alerta, pregunta="Puedes agregar otro intento o tocar Listo.")
    elif accion == "nc_otra":
        negocio.set_espera(chat_id, alerta_id, "nota_intento")
        _responder_callback(token, cq["id"])
        _mostrar_no_contesto(
            token,
            alerta,
            pregunta="✍️ Escribe en un mensaje lo que hiciste (por ejemplo: llamé dos veces, fue al buzón).",
        )
    elif accion == "nc_listo":
        negocio.limpiar_espera(chat_id)
        _responder_callback(token, cq["id"])
        _mostrar_no_contesto(token, alerta, con_botones=False)
    elif accion == "esperar":
        negocio.set_espera(chat_id, alerta_id, "fecha")
        _responder_callback(token, cq["id"])
        _pedir_dato(
            token,
            alerta,
            "\U0001f4c5 <b>Pidió esperar.</b> Responde con la fecha en que hay que volver a contactar (formato DD/MM/AAAA).",
        )
    elif accion == "proveedor":
        negocio.set_espera(chat_id, alerta_id, "nota")
        _responder_callback(token, cq["id"])
        _pedir_dato(token, alerta, "\U0001f4dd <b>Cambió de proveedor.</b> Responde con el motivo.")
    elif accion == "no_aplica":
        negocio.set_espera(chat_id, alerta_id, "nota_no_aplica")
        _responder_callback(token, cq["id"])
        _pedir_dato(
            token,
            alerta,
            "\U0001f6ab <b>No aplica.</b> Responde con el motivo (por ejemplo: cerró la empresa, ya no usa el filtro, "
            "la venta no se va a facturar). Se deja de avisar de este caso.",
        )
    else:
        _responder_callback(token, cq["id"])


def _procesar_invitacion(token, chat_id, codigo_invitacion):
    inv = negocio.resolver_invitacion(codigo_invitacion)
    if not inv:
        _mandar_mensaje(token, chat_id, "Ese link de invitacion no es valido. Pide uno nuevo.")
        return
    if inv["usado_en"]:
        _mandar_mensaje(token, chat_id, "Ese link ya se uso antes. Pide uno nuevo si hace falta.")
        return
    negocio.agregar_chat_telegram(chat_id, inv["nombre"], usuario_id=inv["usuario_id"])
    negocio.marcar_invitacion_usada(codigo_invitacion)
    _mandar_mensaje(
        token,
        chat_id,
        f"✅ Listo, {inv['nombre']}. Ya vas a recibir aqui los avisos de recontacto.",
    )


def _procesar_mensaje_texto(token, msg):
    chat_id = str(msg["chat"]["id"])
    texto = (msg.get("text") or "").strip()
    if not texto:
        return

    if texto.startswith("/start"):
        partes = texto.split(maxsplit=1)
        if len(partes) == 2:
            _procesar_invitacion(token, chat_id, partes[1].strip())
        else:
            _mandar_mensaje(token, chat_id, "Hola. Para activar tus avisos, usa el link que te compartieron.")
        return

    if texto.startswith("/") and _procesar_comando(token, chat_id, texto):
        return

    espera = negocio.get_espera(chat_id)
    if not espera:
        return

    alerta = negocio.obtener_alerta_telegram(espera["alerta_id"])
    if not alerta:
        negocio.limpiar_espera(chat_id)
        return

    if espera["tipo"] == "fecha":
        try:
            fecha = datetime.strptime(texto, "%d/%m/%Y").date().isoformat()
        except ValueError:
            _mandar_mensaje(token, chat_id, "Fecha no válida. Usa el formato DD/MM/AAAA, por ejemplo 15/10/2026.")
            return
        quien = _quien(chat_id, msg.get("from"))
        negocio.registrar_seguimiento(
            alerta["clave_cliente"], alerta["codigo"], "contactado_esperar", fecha, None, f"{quien} (Telegram)"
        )
        negocio.limpiar_espera(chat_id)
        fecha_legible = datetime.fromisoformat(fecha).strftime("%d/%m/%Y")
        _confirmar_y_cerrar(token, alerta, "contactado_esperar", extra=f" hasta el {fecha_legible}", quien=quien)
    elif espera["tipo"] == "nota_intento":
        negocio.limpiar_espera(chat_id)
        ultimo = negocio.ultimo_seguimiento(alerta["clave_cliente"], alerta["codigo"])
        if not ultimo or ultimo["resultado"] != "no_contesto":
            return  # el aviso ya cambio de estado: no se pega la nota a otro seguimiento
        negocio.agregar_nota_ultimo_seguimiento(alerta["clave_cliente"], alerta["codigo"], texto)
        _mostrar_no_contesto(token, alerta, pregunta="Puedes agregar otro intento o tocar Listo.")
    elif espera["tipo"] == "nota_no_aplica":
        if len(texto) < 3:
            _mandar_mensaje(token, chat_id, "Escribe el motivo (al menos unas palabras).")
            return
        quien = _quien(chat_id, msg.get("from"))
        negocio.registrar_seguimiento(
            alerta["clave_cliente"], alerta["codigo"], "no_aplica", None, texto, f"{quien} (Telegram)"
        )
        negocio.limpiar_espera(chat_id)
        _confirmar_y_cerrar(token, alerta, "no_aplica", extra=f": {html.escape(texto)}", quien=quien)
    elif espera["tipo"] == "nota":
        quien = _quien(chat_id, msg.get("from"))
        negocio.registrar_seguimiento(
            alerta["clave_cliente"], alerta["codigo"], "cambio_proveedor", None, texto, f"{quien} (Telegram)"
        )
        negocio.limpiar_espera(chat_id)
        _confirmar_y_cerrar(token, alerta, "cambio_proveedor", extra=f": {html.escape(texto)}", quien=quien)


def main():
    cfg = _cfg()
    token = cfg["token"]
    offset = _leer_offset()
    try:
        _api(token, "setMyCommands", {"commands": _COMANDOS})
    except requests.RequestException as e:
        print(f"No se pudo publicar el menu de comandos: {e}")
    print("Bot de Telegram escuchando... (Ctrl+C para detener)")

    while True:
        try:
            actualizaciones = _api(token, "getUpdates", {"offset": offset, "timeout": 30}) or []
        except requests.RequestException as e:
            print(f"Error de red, reintentando en 5s: {e}")
            time.sleep(5)
            continue

        for u in actualizaciones:
            offset = u["update_id"] + 1
            if "callback_query" in u:
                _procesar_callback(token, u["callback_query"])
            elif "message" in u:
                _procesar_mensaje_texto(token, u["message"])
            _guardar_offset(offset)


if __name__ == "__main__":
    main()
