"""Revision diaria de salud de servidor. Avisa por Telegram a los
administradores solo si algo esta mal (y un "todo en orden" los lunes, para
saber que la propia revision sigue funcionando).

Revisa: servicios (filtros, cnv, taller, Caddy, PostgreSQL), que cada sitio
responda por HTTPS con certificado vigente, conexion a las bases de ERP,
frescura del respaldo y espacio en disco.

Usa un bot propio si existe config/salud_config.json ({"token": "..."});
si no, cae al bot de los recordatorios. Los destinatarios son los usuarios
administradores con Telegram enlazado.

Pensado para correr una vez al dia (systemd timer).
Uso:  python -m app.jobs.salud             (resumen diario: avisa solo si hay problemas)
      python -m app.jobs.salud --siempre   (prueba: manda el reporte completo ya)
      python -m app.jobs.salud --monitor   (vigilancia continua, cada 2 min por systemd:
                                   avisa al aparecer un problema si persiste 2
                                   corridas, recuerda cada 6 h y avisa al resolverse)
"""

import argparse
import json
import os
import re
import shutil
import socket
import ssl
import subprocess
import sys
import time
from datetime import date, datetime, timedelta

from app import auth, negocio
from app.config import RAIZ, ruta_config
from app.telegram import avisos

_CONFIG_SALUD = ruta_config("salud_config.json")
_ESTADO = ruta_config("salud_estado.json")

DOMINIOS = ["filtros.ejemplo.com", "filtros.ejemplo.com", "filtros.ejemplo.com", "filtros.ejemplo.com"]
SERVICIOS = [
    "filtros-erp.service",
    "filtros-erp-bot.service",
    "configurador-cnv.service",
    "formulario-reparacion.service",
    "caddy.service",
    "postgresql.service",
]
TAREAS = ["filtros-erp-alertas.service", "filtros-erp-respaldo.service"]
DIAS_MIN_CERT = 14
HORAS_MAX_RESPALDO = 26
PORCENTAJE_MIN_DISCO = 10
CONFIRMACIONES = 2  # corridas seguidas antes de avisar (evita falsas alarmas de segundos)
RECORDATORIO_HORAS = 6  # cada cuanto se recuerda un problema que sigue sin resolverse


def revisar_servicios():
    problemas = []
    for s in SERVICIOS:
        r = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True)
        estado = r.stdout.strip() or "desconocido"
        if estado != "active":
            problemas.append(f"Servicio {s} está '{estado}'")
    for t in TAREAS:
        r = subprocess.run(["systemctl", "is-failed", t], capture_output=True, text=True)
        if r.stdout.strip() == "failed":
            problemas.append(f"La tarea {t} falló en su última ejecución")
    return problemas


def _conectar_tls(dominio, host="127.0.0.1", puerto=443):
    ctx = ssl.create_default_context()
    sock = socket.create_connection((host, puerto), timeout=10)
    return ctx.wrap_socket(sock, server_hostname=dominio)


def dias_restantes_certificado(dominio, host="127.0.0.1", puerto=443):
    with _conectar_tls(dominio, host, puerto) as ssock:
        cert = ssock.getpeercert()
    return int((ssl.cert_time_to_seconds(cert["notAfter"]) - time.time()) // 86400)


def codigo_http(dominio, host="127.0.0.1", puerto=443):
    """Pide / por HTTPS a traves de Caddy y regresa el codigo de estado."""
    with _conectar_tls(dominio, host, puerto) as ssock:
        ssock.sendall(f"GET / HTTP/1.1\r\nHost: {dominio}\r\nConnection: close\r\n\r\n".encode())
        primera = ssock.recv(200).split(b"\r\n", 1)[0].decode("latin-1")
    return int(primera.split()[1])


def revisar_sitios():
    problemas = []
    for d in DOMINIOS:
        try:
            dias = dias_restantes_certificado(d)
            codigo = codigo_http(d)
        except (OSError, ssl.SSLError, ValueError, IndexError) as e:
            problemas.append(f"Sitio {d}: no responde por HTTPS ({e.__class__.__name__})")
            continue
        if dias < DIAS_MIN_CERT:
            problemas.append(f"Certificado de {d} vence en {dias} días y no se ha renovado")
        if codigo >= 500:
            problemas.append(f"Sitio {d} responde error HTTP {codigo}")
    return problemas


def revisar_erp():
    from app import erp

    problemas = []
    for base in (erp.LEGACY_DB, erp.ACTUAL_DB):
        try:
            conn = erp.conectar(base)
            try:
                conn.cursor().execute("SELECT 1").fetchone()
            finally:
                conn.close()
        except Exception as e:
            problemas.append(f"Sin conexión a la base {base} de ERP ({e.__class__.__name__})")
    return problemas


def revisar_respaldo():
    carpeta = ruta_config("respaldos")
    if not os.path.isdir(carpeta):
        return ["No existe la carpeta de respaldos"]
    archivos = [os.path.join(carpeta, n) for n in os.listdir(carpeta)]
    archivos = [a for a in archivos if os.path.isfile(a)]
    if not archivos:
        return ["No hay ningún respaldo de negocio.db"]
    horas = (time.time() - max(os.path.getmtime(a) for a in archivos)) / 3600
    if horas > HORAS_MAX_RESPALDO:
        return [f"El último respaldo de negocio.db tiene {int(horas)} horas"]
    return []


def revisar_disco():
    uso = shutil.disk_usage(RAIZ)
    libre = uso.free * 100 / uso.total
    if libre < PORCENTAJE_MIN_DISCO:
        return [f"Poco espacio en disco: {libre:.0f}% libre"]
    return []


# (nombre a mostrar, nombre de la funcion); se resuelve al correr para poder simularlas en pruebas
REVISIONES = [
    ("Servicios (filtros, cnv, taller, Caddy, PostgreSQL)", "revisar_servicios"),
    ("Sitios por HTTPS (certificado y respuesta)", "revisar_sitios"),
    ("Conexión a ERP", "revisar_erp"),
    ("Respaldo de negocio.db", "revisar_respaldo"),
    ("Espacio en disco", "revisar_disco"),
]


def cargar_token():
    """Bot propio de salud si esta configurado; si no, el de los recordatorios."""
    if os.path.exists(_CONFIG_SALUD):
        with open(_CONFIG_SALUD, encoding="utf-8") as f:
            return json.load(f)["token"]
    return avisos.cargar_config()["token"]


def chats_admin():
    ids_admin = {u["id"] for u in auth.listar_usuarios() if u["rol"] == "admin"}
    chats = [c["chat_id"] for c in negocio.listar_chats_telegram() if c["usuario_id"] in ids_admin]
    if not chats:
        chats = list(avisos.cargar_config().get("chat_ids", []))
    return list(dict.fromkeys(str(c) for c in chats))


def _clave(texto):
    """Identidad estable de un problema: sin numeros (dias, horas, %) que cambian."""
    return re.sub(r"\d+", "#", texto)


def _leer_estado():
    try:
        with open(_ESTADO, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _guardar_estado(estado):
    tmp = _ESTADO + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False)
    os.replace(tmp, _ESTADO)


def evaluar_monitor(actuales, estado, ahora):
    """Compara los problemas de ahora con la corrida anterior. Regresa
    (mensajes_a_mandar, estado_nuevo). Un problema se avisa cuando lleva
    CONFIRMACIONES corridas seguidas, se recuerda cada RECORDATORIO_HORAS y
    se avisa su resolucion (solo si antes se aviso)."""
    previos = estado.get("problemas", {})
    nuevo = {}
    nuevos, recordar = [], []
    for texto in actuales:
        clave = _clave(texto)
        e = dict(previos.get(clave, {}))
        e["vistos"] = e.get("vistos", 0) + 1
        e["texto"] = texto
        if e["vistos"] >= CONFIRMACIONES:
            if not e.get("avisado"):
                nuevos.append(texto)
                e["avisado"] = ahora.isoformat()
            elif ahora - datetime.fromisoformat(e["avisado"]) >= timedelta(hours=RECORDATORIO_HORAS):
                recordar.append(texto)
                e["avisado"] = ahora.isoformat()
        nuevo[clave] = e
    resueltos = [e["texto"] for k, e in previos.items() if k not in nuevo and e.get("avisado")]

    def lista(titulo, textos):
        return titulo + "\n\n" + "\n".join(f"• {t}" for t in textos)

    mensajes = []
    if nuevos:
        mensajes.append(lista("⚠️ <b>Problema detectado</b>", nuevos))
    if recordar:
        mensajes.append(lista("🔁 <b>Sigue sin resolverse</b>", recordar))
    if resueltos:
        mensajes.append(lista("✅ <b>Resuelto</b>", resueltos))
    return mensajes, {"problemas": nuevo}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--siempre", action="store_true", help="manda el reporte completo aunque todo este bien (prueba)"
    )
    parser.add_argument("--monitor", action="store_true", help="vigilancia continua: avisa solo cuando algo cambia")
    args = parser.parse_args()

    # Que un caracter que la consola no soporte nunca impida mandar el aviso.
    sys.stdout.reconfigure(errors="replace")

    resultados = []
    for nombre, funcion in REVISIONES:
        try:
            problemas = globals()[funcion]()
        except Exception as e:
            problemas = [f"La revisión no pudo correr ({e.__class__.__name__})"]
        resultados.append((nombre, problemas))
    todos = [p for _, ps in resultados for p in ps]

    if args.monitor:
        mensajes, nuevo = evaluar_monitor(todos, _leer_estado(), datetime.now())
        if mensajes:
            token = cargar_token()
            chats = chats_admin()
            for texto in mensajes:
                print(texto)
                for chat in chats:
                    avisos.enviar_mensaje(token, chat, texto)
        _guardar_estado(nuevo)  # solo si el envio no fallo: si falla, se reintenta en la siguiente corrida
        return

    if args.siempre:
        lineas = []
        for nombre, ps in resultados:
            lineas.append(("❌ " if ps else "✅ ") + nombre)
            lineas += [f"    • {p}" for p in ps]
        titulo = "Reporte de salud (prueba)" if not todos else "Reporte de salud (prueba): hay problemas"
        texto = f"\U0001fa7a <b>{titulo}</b>\n\n" + "\n".join(lineas)
    elif todos:
        texto = "⚠️ <b>Revisión diaria: hay problemas</b>\n\n" + "\n".join(f"• {p}" for p in todos)
    elif date.today().weekday() == 0:
        texto = "✅ <b>Sistema en orden</b> (revisión semanal): servicios, sitios, ERP, respaldo y disco bien."
    else:
        print("Todo en orden, no se manda nada.")
        return

    print(texto)
    token = cargar_token()
    for chat in chats_admin():
        avisos.enviar_mensaje(token, chat, texto)


if __name__ == "__main__":
    main()
