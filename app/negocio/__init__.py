"""Base propia del sistema (SQLite, config/negocio.db) y las reglas que deciden el estado de cada caso.

Guarda lo que ERP no tiene: vida util por filtro, maquinas por cliente, seguimientos, usuarios,
destinatarios y avisos de Telegram, bloqueo de login y bitacora de cambios.

Un modulo por tema:
- conexion:      conectar() y el esquema (las tablas se crean y migran solas).
- catalogo:      filtros vigilados, vida util y maquinas.
- estados:       calcular_proximo_contacto y resolver_estado (el modelo de estados; plazos arriba).
- seguimientos:  registrar y consultar los contactos con clientes.
- resultados:    estadisticas de la pestana Resultados y ciclo de "volvio a comprar" sin factura.
- telegram:      avisos enviados, lo que el bot espera, destinatarios e invitaciones.
- seguridad:     bloqueo de login y bitacora de cambios.

Este archivo reexporta lo publico para usarlo como `from app import negocio; negocio.set_vida_util(...)`.
Ver docs/ARQUITECTURA.md.
"""

from app.negocio.catalogo import (
    agregar_filtro,
    get_maquinas,
    get_vida_util,
    listar_filtros,
    listar_maquinas,
    listar_vida_util,
    seed_filtros,
    set_maquinas,
    set_vida_util,
)
from app.negocio.conexion import conectar
from app.negocio.estados import (
    DIAS_LIMITE_FACTURA,
    DIAS_POR_MES,
    DIAS_PRORROGA_FACTURA,
    DIAS_REINTENTO,
    RESULTADOS,
    calcular_proximo_contacto,
    resolver_estado,
)
from app.negocio.resultados import (
    PREFIJO_DEMO,
    compras_demo,
    reclasificar_por_compras,
    resumen_seguimientos,
    sin_factura,
    ventas_registradas,
)
from app.negocio.seguimientos import (
    agregar_nota_ultimo_seguimiento,
    historial_seguimiento,
    listar_seguimientos,
    registrar_seguimiento,
    ultimo_seguimiento,
)
from app.negocio.seguridad import (
    esta_bloqueado,
    historial_config,
    limpiar_intentos,
    registrar_cambio_config,
    registrar_intento_fallido,
)
from app.negocio.telegram import (
    actualizar_message_id,
    agregar_chat_telegram,
    crear_invitacion_telegram,
    descartar_alerta_telegram,
    dias_desde_ultimo_aviso,
    get_espera,
    guardar_texto_alerta,
    limpiar_espera,
    listar_chats_telegram,
    marcar_alerta_resuelta,
    marcar_invitacion_usada,
    obtener_alerta_telegram,
    quitar_chat_telegram,
    registrar_alerta_telegram,
    resolver_invitacion,
    set_espera,
)

__all__ = [
    "DIAS_LIMITE_FACTURA",
    "DIAS_POR_MES",
    "DIAS_PRORROGA_FACTURA",
    "DIAS_REINTENTO",
    "PREFIJO_DEMO",
    "RESULTADOS",
    "actualizar_message_id",
    "agregar_chat_telegram",
    "agregar_filtro",
    "agregar_nota_ultimo_seguimiento",
    "calcular_proximo_contacto",
    "compras_demo",
    "conectar",
    "crear_invitacion_telegram",
    "descartar_alerta_telegram",
    "dias_desde_ultimo_aviso",
    "esta_bloqueado",
    "get_espera",
    "get_maquinas",
    "get_vida_util",
    "guardar_texto_alerta",
    "historial_config",
    "historial_seguimiento",
    "limpiar_espera",
    "limpiar_intentos",
    "listar_chats_telegram",
    "listar_filtros",
    "listar_maquinas",
    "listar_seguimientos",
    "listar_vida_util",
    "marcar_alerta_resuelta",
    "marcar_invitacion_usada",
    "obtener_alerta_telegram",
    "quitar_chat_telegram",
    "reclasificar_por_compras",
    "registrar_alerta_telegram",
    "registrar_cambio_config",
    "registrar_intento_fallido",
    "registrar_seguimiento",
    "resolver_estado",
    "resolver_invitacion",
    "resumen_seguimientos",
    "seed_filtros",
    "set_espera",
    "set_maquinas",
    "set_vida_util",
    "sin_factura",
    "ultimo_seguimiento",
    "ventas_registradas",
]
