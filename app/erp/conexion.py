"""Conexion a las dos bases de ERP (SQL Server, solo lectura) y constantes de lo que se lee de ellas.

La conexion sale de config/db_config.json. Nunca se escribe en ERP.
"""

import json

import pyodbc

from app.config import ruta_config

RUTA_CONFIG = ruta_config("db_config.json")

# Solo se consideran compras desde esta fecha.
FECHA_INICIO = "2024-01-01"

# Conceptos de "Factura de venta" en el sistema anterior (Aspel), todas las
# sucursales, sin notas de crédito ni devoluciones.
LEGACY_DB = "adERP_MX_2021"
LEGACY_CONCEPTOS_FACTURA = (4, 5, 3012, 3013, 3014, 3015, 3016, 3017, 3018, 3178, 3209, 3221, 3266)

# Sistema actual (Compac): módulo "Facturas CFDi", tipo de documento 5.
ACTUAL_DB = "ERP_Comercial"
ACTUAL_MODULE_ID = 21
ACTUAL_DOCUMENT_TYPE_ID = 5


def _cfg():
    with open(RUTA_CONFIG, encoding="utf-8") as f:
        return json.load(f)


def conectar(database):
    """Abre una conexion a la base `database` (LEGACY_DB o ACTUAL_DB)."""
    cfg = _cfg()
    conn_str = (
        f"DRIVER={{{cfg['driver']}}};"
        f"SERVER={cfg['server']};"
        f"DATABASE={database};"
        f"UID={cfg['uid']};"
        f"PWD={cfg['pwd']};"
        f"Encrypt={cfg['encrypt']};"
        f"TrustServerCertificate={cfg['trust_server_certificate']};"
    )
    return pyodbc.connect(conn_str, timeout=15)


def temp_codigos(cur, codigos, collate=None):
    """Crea la tabla temporal #Filtros con los codigos, para usarla en los JOIN de las consultas."""
    collate_clause = f" COLLATE {collate}" if collate else ""
    cur.execute("IF OBJECT_ID('tempdb..#Filtros') IS NOT NULL DROP TABLE #Filtros")
    cur.execute(f"CREATE TABLE #Filtros (Codigo NVARCHAR(100){collate_clause} PRIMARY KEY)")
    cur.executemany("INSERT INTO #Filtros (Codigo) VALUES (?)", [(c,) for c in codigos])


def normalizar_nombre(nombre):
    """Normaliza un nombre de cliente para emparejar el mismo cliente real
    entre las dos bases (que no comparten ids)."""
    return " ".join((nombre or "").split()).strip().upper()
