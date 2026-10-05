"""Copia config/negocio.db a config/respaldos/negocio-YYYY-MM-DD.db y borra
los respaldos de mas de 30 dias. negocio.db guarda todo lo que ERP no
tiene (vida util, maquinas, seguimientos, usuarios), asi que es el unico
archivo del proyecto que de verdad se pierde si se corrompe.

La copia usa la API de respaldo de SQLite: es consistente aunque alguien
este guardando datos en ese momento, y el archivo nuevo lleva la fecha de
hoy (no la de la ultima edicion de la base). Los de mas de 30 dias se
borran segun la fecha del nombre del archivo.
Pensado para correr una vez al dia (systemd timer / Programador de tareas).
Uso: python -m app.jobs.respaldo
"""

import os
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta

from app.config import ruta_config

_DB = ruta_config("negocio.db")
_DIR_RESPALDOS = ruta_config("respaldos")
_DIAS_A_CONSERVAR = 30


def main():
    if not os.path.exists(_DB):
        print("No existe config/negocio.db, nada que respaldar.")
        return 0
    os.makedirs(_DIR_RESPALDOS, exist_ok=True)
    destino = os.path.join(_DIR_RESPALDOS, f"negocio-{date.today().isoformat()}.db")

    origen = sqlite3.connect(_DB)
    copia = sqlite3.connect(destino)
    try:
        origen.backup(copia)
        estado = copia.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        copia.close()
        origen.close()
    if estado != "ok":
        print(f"ERROR: el respaldo {destino} no paso la verificacion de integridad ({estado})")
        return 1
    print(f"Respaldo guardado en {destino}")

    limite = date.today() - timedelta(days=_DIAS_A_CONSERVAR)
    borrados = 0
    for nombre in os.listdir(_DIR_RESPALDOS):
        m = re.fullmatch(r"negocio-(\d{4}-\d{2}-\d{2})\.db", nombre)
        if not m:
            continue
        if datetime.strptime(m.group(1), "%Y-%m-%d").date() < limite:
            os.remove(os.path.join(_DIR_RESPALDOS, nombre))
            borrados += 1
    if borrados:
        print(f"Se borraron {borrados} respaldo(s) de mas de {_DIAS_A_CONSERVAR} dias.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
