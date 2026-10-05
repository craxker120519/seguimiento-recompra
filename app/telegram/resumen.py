"""Mensajes de Telegram que NO son una alerta individual:

- resumen diario: una sola lista con todo lo que toca contactar (vencido o por
  vencer en 7 dias), para no depender de revisar mensaje por mensaje.
- escalacion: alertas que llevan varios dias vencidas sin que nadie las atienda,
  dirigidas solo a los administradores.

Las funciones de texto/seleccion son puras (reciben las alertas y la fecha de
hoy) para poder probarlas sin Telegram ni base de datos."""

import html
import json
import os
from datetime import date

from app import auth, negocio
from app.config import ruta_config

_ESTADO_ESCALACION = ruta_config("escalacion_estado.json")
_ESTADO_FACTURAS = ruta_config("facturas_pendientes_estado.json")

MAX_LINEAS = 15
DIAS_SEMANA_RESUMEN = (0, 1, 2, 3, 4, 5)  # lunes a sabado
DIAS_ESCALAR = 5  # dias vencida sin atender antes de avisar a los administradores
DIAS_REESCALAR = 7  # cada cuantos dias se vuelve a avisar de la misma alerta
DIAS_FACTURA_PENDIENTE = 7  # "volvio a comprar" sin factura: primer aviso a la semana y luego cada semana

_MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
_DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def _fecha_corta(iso):
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {_MESES[d.month - 1]}"


def _dias_vencida(alerta, hoy):
    return (hoy - date.fromisoformat(alerta["proximo_contacto"][:10])).days


def _linea(a, hoy):
    dias = _dias_vencida(a, hoy)
    if dias > 0:
        cuando = f"venció {_fecha_corta(a['proximo_contacto'])} · hace {dias} día{'s' if dias != 1 else ''}"
        icono = "\U0001f534"
    elif dias == 0:
        cuando = "vence hoy"
        icono = "\U0001f534"
    else:
        cuando = f"vence {_fecha_corta(a['proximo_contacto'])}"
        icono = "\U0001f7e0"
    producto = html.escape(a.get("nombre_producto") or "")
    if len(producto) > 45:
        producto = producto[:44] + "…"
    texto = (
        f"{icono} <b>{html.escape(a['cliente'] or '')}</b>\n    {html.escape(a['codigo'])} — {producto}\n    {cuando}"
    )
    if a.get("estado") == "factura_vencida":
        texto += f"\n    \U0001f9fe vendió el {_fecha_corta(a['nota_estado'])}, sin factura"
    return texto


def hay_resumen_hoy(cfg, hoy):
    """El resumen se manda de lunes a sabado, salvo que telegram_config.json
    lo apague ("resumen_diario": false) o cambie los dias ("resumen_dias": [0..6])."""
    if cfg.get("resumen_diario", True) is False:
        return False
    return hoy.weekday() in cfg.get("resumen_dias", DIAS_SEMANA_RESUMEN)


def texto_resumen(alertas, hoy, maximo=MAX_LINEAS):
    """Una sola lista con lo que toca contactar. None si no hay nada."""
    if not alertas:
        return None
    vencidas = [a for a in alertas if _dias_vencida(a, hoy) >= 0]
    por_vencer = [a for a in alertas if _dias_vencida(a, hoy) < 0]
    encabezado = (
        f"\U0001f4cb <b>Resumen del día · {_DIAS[hoy.weekday()]} {hoy.day} {_MESES[hoy.month - 1]}</b>\n"
        f"\U0001f534 Vencidos: <b>{len(vencidas)}</b>   \U0001f7e0 Por vencer (7 días): <b>{len(por_vencer)}</b>"
    )
    ordenadas = sorted(alertas, key=lambda a: a["proximo_contacto"])
    lineas = [_linea(a, hoy) for a in ordenadas[:maximo]]
    texto = encabezado + "\n\n" + "\n\n".join(lineas)
    resto = len(ordenadas) - maximo
    if resto > 0:
        texto += f"\n\n… y {resto} más. Míralos en la pestaña «Contactar hoy»."
    return texto


def _leer_estado():
    try:
        with open(_ESTADO_ESCALACION, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_estado(estado):
    tmp = _ESTADO_ESCALACION + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(tmp, _ESTADO_ESCALACION)


def _clave(a):
    return f"{a['clave_cliente']}|{a['codigo']}"


def seleccionar_escalacion(alertas, estado, hoy, dias_escalar=DIAS_ESCALAR, dias_reescalar=DIAS_REESCALAR):
    """Alertas vencidas hace `dias_escalar` dias o mas que no se han avisado a los
    administradores en los ultimos `dias_reescalar` dias. Una alerta atendida
    (con seguimiento) deja de estar vencida por si sola, asi que no aparece aqui."""
    elegidas = []
    for a in alertas:
        if _dias_vencida(a, hoy) < dias_escalar:
            continue
        ultimo = estado.get(_clave(a))
        if ultimo and (hoy - date.fromisoformat(ultimo)).days < dias_reescalar:
            continue
        elegidas.append(a)
    elegidas.sort(key=lambda a: a["proximo_contacto"])
    return elegidas


def texto_escalacion(elegidas, hoy, dias_escalar=DIAS_ESCALAR, maximo=MAX_LINEAS):
    if not elegidas:
        return None
    lineas = [_linea(a, hoy) for a in elegidas[:maximo]]
    texto = (
        f"\U0001f6a8 <b>Sin atender: {len(elegidas)} alerta{'s' if len(elegidas) != 1 else ''} "
        f"con más de {dias_escalar} días vencida{'s' if len(elegidas) != 1 else ''}</b>\n"
        "Ya pasó su fecha y nadie ha registrado un seguimiento nuevo.\n\n" + "\n\n".join(lineas)
    )
    resto = len(elegidas) - maximo
    if resto > 0:
        texto += f"\n\n… y {resto} más."
    return texto


def chats_admin(cfg):
    """Chats de Telegram enlazados a usuarios administradores; si no hay
    ninguno, los chats fijos de telegram_config.json."""
    ids_admin = {u["id"] for u in auth.listar_usuarios() if u["rol"] == "admin"}
    chats = [c["chat_id"] for c in negocio.listar_chats_telegram() if c["usuario_id"] in ids_admin]
    if not chats:
        chats = list(cfg.get("chat_ids", []))
    return list(dict.fromkeys(str(c) for c in chats))


def marcar_escaladas(elegidas, hoy):
    estado = _leer_estado()
    for a in elegidas[:MAX_LINEAS]:
        estado[_clave(a)] = hoy.isoformat()
    # Se olvidan las de hace mas de 60 dias para que el archivo no crezca sin fin.
    estado = {k: v for k, v in estado.items() if (hoy - date.fromisoformat(v)).days <= 60}
    _guardar_estado(estado)


def estado_escalacion():
    return _leer_estado()


# ---- "Volvio a comprar" registrado a mano pero sin factura en ERP ----


def _leer_json(ruta):
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_json(ruta, datos):
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False)
    os.replace(tmp, ruta)


def estado_facturas():
    return _leer_json(_ESTADO_FACTURAS)


def facturas_pendientes(ventas, compras):
    """Ventas registradas a mano ("volvio a comprar") cuya factura aun no aparece en ERP."""
    return [v for v in ventas if negocio.sin_factura(v["clave_cliente"], v["codigo"], v["fecha"], compras)]


def seleccionar_facturas(pendientes, estado, hoy, dias=DIAS_FACTURA_PENDIENTE, limite=negocio.DIAS_LIMITE_FACTURA):
    """Las que ya cumplieron `dias` dias desde que se registro la venta (la semana de
    prorroga) y no se han avisado en los ultimos `dias` dias (asi: a la semana, y luego
    cada semana). Al cumplir `limite` dias (15) dejan de ser un simple recordatorio: pasan
    a ser una alerta vencida de contacto, que se avisa por el flujo normal de alertas."""
    elegidas = []
    for v in pendientes:
        transcurridos = (hoy - date.fromisoformat(v["fecha"][:10])).days
        if transcurridos < dias or transcurridos >= limite:
            continue
        ultimo = estado.get(_clave(v))
        if ultimo and (hoy - date.fromisoformat(ultimo)).days < dias:
            continue
        elegidas.append(v)
    elegidas.sort(key=lambda v: v["fecha"])
    return elegidas


def texto_facturas(elegidas, hoy, nombres=None, maximo=MAX_LINEAS):
    if not elegidas:
        return None
    nombres = nombres or {}
    lineas = []
    for v in elegidas[:maximo]:
        dias = (hoy - date.fromisoformat(v["fecha"][:10])).days
        producto = html.escape(nombres.get(v["codigo"], ""))
        if len(producto) > 45:
            producto = producto[:44] + "…"
        faltan = negocio.DIAS_LIMITE_FACTURA - dias
        lineas.append(
            f"\U0001f7e1 <b>{html.escape(v['clave_cliente'] or '')}</b>\n"
            f"    {html.escape(v['codigo'])}{' — ' + producto if producto else ''}\n"
            f"    registrado {_fecha_corta(v['fecha'])} · hace {dias} días · "
            f"pasa a vencido en {faltan} día{'s' if faltan != 1 else ''}"
        )
    texto = (
        f"\U0001f9fe <b>Volvieron a comprar, pero aún no hay factura ({len(elegidas)})</b>\n"
        "Cuando se facture en ERP, el sistema calcula solo el próximo contacto. "
        f"Si no llega la factura a los {negocio.DIAS_LIMITE_FACTURA} días, pasa a vencido y habrá que contactar al cliente.\n\n"
        + "\n\n".join(lineas)
    )
    resto = len(elegidas) - maximo
    if resto > 0:
        texto += f"\n\n… y {resto} más."
    return texto


def marcar_facturas_avisadas(elegidas, pendientes, hoy):
    """Guarda cuando se aviso cada una; olvida las que ya no estan pendientes (ya se facturaron)."""
    estado = _leer_json(_ESTADO_FACTURAS)
    for v in elegidas[:MAX_LINEAS]:
        estado[_clave(v)] = hoy.isoformat()
    vigentes = {_clave(v) for v in pendientes}
    _guardar_json(_ESTADO_FACTURAS, {k: d for k, d in estado.items() if k in vigentes})


# ---- consultas desde Telegram (/hoy, /cliente) ----


def texto_estado(estado, proximo, nota, hoy):
    """Una linea con el estado de un cliente+producto, igual de claro que la etiqueta de la pagina."""

    def f(iso):
        return _fecha_corta(iso) if iso else "?"

    if estado == "pendiente":
        return f"\u23f8 Pidió esperar hasta {f(proximo)}"
    if estado == "resuelto":
        return "\u2705 Volvió a comprar"
    if estado == "inactivo":
        return "\u26aa Cambió de proveedor" + (f": {html.escape(nota)}" if nota else "")
    if estado == "descartado":
        return "\u26aa No aplica" + (f": {html.escape(nota)}" if nota else "")
    if estado == "reintentar":
        cuando = (
            "ya toca reintentar" if proximo and date.fromisoformat(proximo[:10]) <= hoy else f"reintentar {f(proximo)}"
        )
        return f"\U0001f4f5 No contestó el {f(nota)} · {cuando}"
    if estado == "esperando_factura":
        return f"\u23f3 Volvió a comprar el {f(nota)} · esperando factura (si no llega, vence el {f(proximo)})"
    if estado == "factura_vencida":
        return f"\U0001f534 Sin factura desde el {f(nota)}: contactar ya"
    if not proximo:
        return "\u2796 Sin fecha: falta vida útil o máquinas"
    dias = (date.fromisoformat(proximo[:10]) - hoy).days
    if dias < 0:
        return f"\U0001f534 Contactar ya (venció el {f(proximo)})"
    if dias <= 7:
        return f"\U0001f7e0 Vence el {f(proximo)}"
    return f"\U0001f7e2 Próximo contacto el {f(proximo)}"


def texto_cliente(datos, hoy, maximo=20):
    """Ficha corta de un cliente (lo que regresa db.timeline_cliente) para Telegram."""
    productos = datos["productos"]
    lineas = []
    for p in productos[:maximo]:
        ultima = p["compras"][0]
        nombre = html.escape(p.get("nombre") or "")
        if len(nombre) > 45:
            nombre = nombre[:44] + "…"
        lineas.append(
            f"<b>{html.escape(p['codigo'])}</b> — {nombre}\n"
            f"    Última compra {_fecha_corta(ultima['fecha'])}\n"
            f"    {texto_estado(p['estado'], ultima.get('proximo_contacto'), p.get('nota_estado'), hoy)}"
        )
    texto = (
        f"\U0001f3ed <b>{html.escape(datos['cliente'] or '(sin nombre)')}</b> · {len(productos)} filtro{'s' if len(productos) != 1 else ''}\n\n"
        + "\n\n".join(lineas)
    )
    if len(productos) > maximo:
        texto += f"\n\n… y {len(productos) - maximo} más. Míralos en la página."
    return texto
