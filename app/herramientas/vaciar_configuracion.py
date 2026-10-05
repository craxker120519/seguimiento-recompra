"""Vacia la vida util de los filtros y las maquinas de cada cliente (tablas vida_util
y maquinas de config/negocio.db). Con --todo vacia ademas todo lo generado por las
pruebas: seguimientos, avisos de Telegram, esperas del bot e historial de cambios.
NUNCA toca usuarios, chats de Telegram, invitaciones ni el catalogo de filtros.

Antes de borrar guarda una copia completa en config/respaldos/negocio-antes-de-vaciar-<fecha>.db
(el respaldo diario no la borra), para poder recuperar los datos si hiciera falta.

Uso:  python -m app.herramientas.vaciar_configuracion                       solo muestra cuantas filas se borrarian
      python -m app.herramientas.vaciar_configuracion --confirmar           respalda y vacia vida util y maquinas
      python -m app.herramientas.vaciar_configuracion --todo --confirmar    ademas vacia seguimientos y avisos
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime

from app.config import ruta_config

_DB = ruta_config("negocio.db")
_DIR_RESPALDOS = ruta_config("respaldos")
TABLAS = ("vida_util", "maquinas")
TABLAS_PRUEBA = ("seguimientos", "alertas_telegram", "telegram_espera", "historial_config")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--confirmar", action="store_true")
    p.add_argument("--todo", action="store_true", help="incluye seguimientos, avisos, esperas e historial")
    args = p.parse_args()
    tablas = TABLAS + (TABLAS_PRUEBA if args.todo else ())

    conn = sqlite3.connect(_DB)
    try:
        cuentas = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tablas}
        for t, n in cuentas.items():
            print(f"  {t}: {n} fila(s)")
        if not args.confirmar:
            print("No se borro nada. Para vaciar de verdad: --confirmar")
            return 0

        os.makedirs(_DIR_RESPALDOS, exist_ok=True)
        destino = os.path.join(_DIR_RESPALDOS, f"negocio-antes-de-vaciar-{datetime.now():%Y-%m-%d_%H%M%S}.db")
        copia = sqlite3.connect(destino)
        try:
            conn.backup(copia)
            if copia.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                print("ERROR: el respaldo no paso la verificacion; no se borro nada.")
                return 1
        finally:
            copia.close()
        print(f"Respaldo guardado en {destino}")

        for t in tablas:
            conn.execute(f"DELETE FROM {t}")
        conn.commit()
        for t in tablas:
            print(f"  {t}: ahora {conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} fila(s)")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
