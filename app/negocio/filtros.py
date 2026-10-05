"""Codigos de los filtros vigilados.

Viven en la tabla `filtros` de la base propia. La primera vez que corre en una maquina (tabla vacia) se
siembran una sola vez desde un Excel; de ahi en adelante el Excel ya no se toca y los altas nuevas se agregan
con agregar_filtro(codigo) (pestana Catalogo).
"""

import os

import openpyxl

from app.config import RAIZ
from app.negocio.catalogo import listar_filtros, seed_filtros

EXCEL_SEMILLA = os.path.join(RAIZ, "data", "filtros_semilla.xlsx")


def _codigos_excel():
    wb = openpyxl.load_workbook(EXCEL_SEMILLA, data_only=True)
    ws = wb["ERP"]
    return sorted(set(row[0] for row in ws.iter_rows(min_row=2, values_only=True) if row[0]))


def codigos_filtro():
    """Codigos de filtro vigilados (siembra desde el Excel si la tabla esta vacia)."""
    existentes = listar_filtros()
    if not existentes:
        codigos_excel = _codigos_excel()
        seed_filtros(codigos_excel)
        existentes = codigos_excel
    return sorted(existentes)
