"""Latido para un monitor externo (Healthchecks.io). Se corre cada minuto
(systemd timer). Si el servidor se apaga, se queda sin luz o sin internet,
los latidos dejan de llegar y el monitor externo avisa; si el servidor sigue
vivo pero la app o Caddy no responden, o el monitor de salud (salud.py
--monitor) dejo de correr, se manda una senal de fallo y avisa al momento.

La URL de ping (secreta) vive en config/latido.url, una sola linea.
Uso: python -m app.jobs.latido
"""

import os
import sys
import time
import urllib.error
import urllib.request

from app.config import ruta_config

RUTA_URL = ruta_config("latido.url")
_ESTADO_MONITOR = ruta_config("salud_estado.json")
SEGUNDOS_REINTENTO = 8  # espera antes de confirmar una falla
MINUTOS_MAX_MONITOR = 10  # el monitor corre cada 2 min y guarda este archivo en cada corrida
APP_URL = "http://127.0.0.1:5057/"
DOMINIO = "filtros.ejemplo.com"


class _SinRedireccion(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def app_responde():
    """La app contesta (un 302 hacia /login es lo normal, no se sigue)."""
    try:
        r = urllib.request.build_opener(_SinRedireccion).open(APP_URL, timeout=8)
        return r.status < 500
    except urllib.error.HTTPError as e:
        return e.code < 500
    except Exception:
        return False


def caddy_responde():
    """Caddy sirve el dominio por HTTPS con certificado valido."""
    try:
        from app.jobs import salud

        return salud.codigo_http(DOMINIO) < 500
    except Exception:
        return False


def minutos_sin_monitor(ahora=None):
    """Minutos desde la ultima corrida completa del monitor de salud (cada corrida
    reescribe salud_estado.json). None si el archivo aun no existe."""
    try:
        return ((ahora or time.time()) - os.path.getmtime(_ESTADO_MONITOR)) / 60
    except OSError:
        return None


def monitor_vivo(ahora=None):
    minutos = minutos_sin_monitor(ahora)
    return minutos is None or minutos <= MINUTOS_MAX_MONITOR


def enviar_ping(url, ok, detalle):
    destino = url if ok else url.rstrip("/") + "/fail"
    ultimo_error = None
    for _ in range(3):
        try:
            req = urllib.request.Request(destino, data=detalle.encode("utf-8"), method="POST")
            urllib.request.urlopen(req, timeout=10).read()
            return
        except Exception as e:
            ultimo_error = e
            time.sleep(3)
    raise RuntimeError(f"no se pudo mandar el latido: {ultimo_error}")


def revisar():
    """Lista de lo que esta mal ahora mismo (vacia si todo responde)."""
    fallas = []
    if not app_responde():
        fallas.append("la app (gunicorn) no responde")
    if not caddy_responde():
        fallas.append("Caddy/HTTPS no responde")
    if not monitor_vivo():
        fallas.append(f"el monitor de salud lleva {int(minutos_sin_monitor())} min sin correr")
    return fallas


def revisar_con_reintento():
    """Una falla se confirma con una segunda revision unos segundos despues: asi un reinicio de la app
    (por ejemplo al desplegar) no manda una falsa alarma."""
    fallas = revisar()
    if fallas:
        time.sleep(SEGUNDOS_REINTENTO)
        fallas = revisar()
    return fallas


def main():
    with open(RUTA_URL, encoding="utf-8") as f:
        url = f.read().strip()

    fallas = revisar_con_reintento()
    if fallas:
        enviar_ping(url, False, "FALLA: " + "; ".join(fallas))
        print("FALLA:", "; ".join(fallas))
    else:
        enviar_ping(url, True, "app, Caddy y monitor responden")
        print("latido OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e)
        sys.exit(1)
