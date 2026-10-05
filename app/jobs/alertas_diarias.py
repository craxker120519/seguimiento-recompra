"""Manda por Telegram, a todos los chats configurados:

1. Un resumen del dia: una sola lista con todo lo que toca contactar (vencido o
   por vencer en los proximos 7 dias). De lunes a sabado; se apaga con
   "resumen_diario": false en config/telegram_config.json.
2. Cada alerta en su propio mensaje, con botones para registrar el seguimiento
   desde Telegram (ver telegram_bot_escuchar.py). Un mismo cliente+filtro se
   vuelve a avisar cada `dias_entre_avisos` dias (3 por defecto) para no
   repetir el mensaje todos los dias.
3. Los que se marcaron "Volvio a comprar" y aun no tienen factura en ERP:
   se avisan a la semana de registrarlos y luego cada semana
   (`dias_factura_pendiente`, 7 por defecto) hasta que la factura aparezca.
4. Solo a los administradores: las alertas que llevan mas de
   `dias_escalar` dias (5 por defecto) vencidas sin que nadie registre
   seguimiento; se vuelven a avisar cada `dias_reescalar` dias (7).

Cada parte corre por separado: si una falla, las demas se mandan igual y el
programa termina con error (para que systemd/salud.py lo noten).

Pensado para correr una vez al dia (systemd timer / Programador de tareas).
Uso: python -m app.jobs.alertas_diarias         (manda todo)
     python -m app.jobs.alertas_diarias --ver   (solo muestra los mensajes, no manda ni marca nada)
"""

import argparse
import sys
from datetime import date

import requests

from app import negocio
from app.erp import alertas_recontacto, catalogo_filtros, ultimas_compras
from app.negocio.filtros import codigos_filtro
from app.telegram import avisos, resumen


def _mandar_a(cfg, chats, texto):
    enviados = 0
    for chat in chats:
        try:
            avisos.enviar_mensaje(cfg["token"], chat, texto)
            enviados += 1
        except requests.RequestException as e:
            print(f"  no se pudo mandar a {chat}: {e.__class__.__name__}")
    return enviados


def _facturas_pendientes(cfg, hoy):
    """(pendientes, elegidas, texto) de las ventas registradas a mano que esperan factura."""
    ventas = negocio.ventas_registradas()
    if not ventas:
        return [], [], None
    codigos = codigos_filtro()
    pendientes = resumen.facturas_pendientes(ventas, ultimas_compras(codigos))
    dias = int(cfg.get("dias_factura_pendiente", resumen.DIAS_FACTURA_PENDIENTE))
    elegidas = resumen.seleccionar_facturas(pendientes, resumen.estado_facturas(), hoy, dias)
    try:
        nombres = {p["codigo"]: p["nombre"] for p in catalogo_filtros(codigos)}
    except Exception:
        nombres = {}
    return pendientes, elegidas, resumen.texto_facturas(elegidas, hoy, nombres)


def ver(cfg, alertas, hoy):
    sys.stdout.reconfigure(errors="replace")
    print(resumen.texto_resumen(alertas, hoy) or "(sin resumen: no hay alertas)")
    print("\n" + "-" * 40 + "\n")
    dias_escalar = int(cfg.get("dias_escalar", resumen.DIAS_ESCALAR))
    elegidas = resumen.seleccionar_escalacion(
        alertas,
        resumen.estado_escalacion(),
        hoy,
        dias_escalar,
        int(cfg.get("dias_reescalar", resumen.DIAS_REESCALAR)),
    )
    print(resumen.texto_escalacion(elegidas, hoy, dias_escalar) or "(sin escalacion)")
    print("\n" + "-" * 40 + "\n")
    print(_facturas_pendientes(cfg, hoy)[2] or "(sin ventas esperando factura por avisar)")


def _parte_alertas(cfg, chats, alertas, hoy):
    if not alertas:
        print("Sin alertas pendientes: no hay resumen ni avisos individuales.")
        return
    if resumen.hay_resumen_hoy(cfg, hoy):
        texto = resumen.texto_resumen(alertas, hoy)
        n = _mandar_a(cfg, chats, texto) if texto else 0
        print(f"Resumen del dia enviado a {n} chat(s).")
    dias = int(cfg.get("dias_entre_avisos", 3))
    enviadas, _ = avisos.enviar_alertas(cfg, chats, alertas, dias_entre_avisos=dias)
    print(f"Enviadas {enviadas} alertas por Telegram ({len(alertas)} pendientes x {len(chats)} chat(s)).")


def _parte_facturas(cfg, chats, hoy):
    pendientes, elegidas, texto = _facturas_pendientes(cfg, hoy)
    if texto and _mandar_a(cfg, chats, texto):
        resumen.marcar_facturas_avisadas(elegidas, pendientes, hoy)
        print(f"Facturas pendientes: {len(elegidas)} venta(s) sin factura avisadas.")
    else:
        resumen.marcar_facturas_avisadas([], pendientes, hoy)  # solo olvida las que ya se facturaron
        print("Facturas pendientes: nada que avisar.")


def _parte_escalacion(cfg, alertas, hoy):
    dias_escalar = int(cfg.get("dias_escalar", resumen.DIAS_ESCALAR))
    dias_reescalar = int(cfg.get("dias_reescalar", resumen.DIAS_REESCALAR))
    elegidas = resumen.seleccionar_escalacion(alertas, resumen.estado_escalacion(), hoy, dias_escalar, dias_reescalar)
    texto = resumen.texto_escalacion(elegidas, hoy, dias_escalar)
    if texto:
        if _mandar_a(cfg, resumen.chats_admin(cfg), texto):
            resumen.marcar_escaladas(elegidas, hoy)
        print(f"Escalacion: {len(elegidas)} alerta(s) sin atender avisadas a los administradores.")
    else:
        print("Escalacion: nada que avisar.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ver", action="store_true", help="solo muestra los mensajes, sin mandar nada")
    args = parser.parse_args()
    cfg = avisos.cargar_config()
    chats = avisos.destinatarios(cfg)
    alertas = alertas_recontacto(codigos_filtro())
    hoy = date.today()
    if args.ver:
        ver(cfg, alertas, hoy)
        return 0

    errores = 0
    for nombre, parte in (
        ("alertas", lambda: _parte_alertas(cfg, chats, alertas, hoy)),
        ("facturas pendientes", lambda: _parte_facturas(cfg, chats, hoy)),
        ("escalacion", lambda: _parte_escalacion(cfg, alertas, hoy)),
    ):
        try:
            parte()
        except Exception as e:
            errores += 1
            print(f"ERROR en {nombre}: {e.__class__.__name__}: {e}")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
