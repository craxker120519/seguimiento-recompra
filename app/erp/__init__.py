"""Lectura de las dos bases de ERP (SQL Server). SOLO LECTURA: el sistema nunca escribe en ERP.

Un modulo por tema:
- conexion:  conexion, constantes (bases, conceptos de factura, fecha de inicio) y normalizar_nombre.
- catalogo:  codigo y nombre de los filtros; busqueda para agregar uno nuevo.
- productos: resumen de ventas y linea de tiempo de un filtro.
- clientes:  busqueda de clientes y linea de tiempo de un cliente.
- compras:   ultima compra de cada cliente y filtro, y alertas_recontacto (la lista de trabajo del dia).

Un mismo cliente puede existir en las dos bases con ids distintos: se junta por su nombre normalizado,
que tambien es la clave_cliente de la base propia (app.negocio).

Este archivo reexporta lo publico para usarlo como `from app import erp; erp.alertas_recontacto(...)`.
"""

from app.erp.catalogo import buscar_catalogo_erp, catalogo_filtros
from app.erp.clientes import buscar_clientes, timeline_cliente
from app.erp.compras import alertas_recontacto, ultimas_compras, ultimas_compras_por_cliente
from app.erp.conexion import (
    ACTUAL_DB,
    FECHA_INICIO,
    LEGACY_DB,
    conectar,
    normalizar_nombre,
)
from app.erp.productos import resumen_combinado, timeline_producto

__all__ = [
    "ACTUAL_DB",
    "FECHA_INICIO",
    "LEGACY_DB",
    "alertas_recontacto",
    "buscar_catalogo_erp",
    "buscar_clientes",
    "catalogo_filtros",
    "conectar",
    "normalizar_nombre",
    "resumen_combinado",
    "timeline_cliente",
    "timeline_producto",
    "ultimas_compras",
    "ultimas_compras_por_cliente",
]
