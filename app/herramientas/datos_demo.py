"""Datos FALSOS para ver como luce la pestaña Resultados con TODA su funcion (y, si se
pide, como llegan por Telegram el resumen diario y la escalacion). Todo cliente falso se
llama "DEMO - ..." y se borra por completo con --borrar. Los clientes DEMO nunca generan
avisos de Telegram por su cuenta.

Tambien crea facturas INVENTADAS (config/demo_compras.json) para mostrar los casos:
  - "Volvio a comprar" con factura                          -> caso normal
  - "Volvio a comprar" sin factura (dias 0-14)              -> esperando factura
  - "Volvio a comprar" sin factura (15 dias o mas)          -> sin factura tras 15 dias: contactar
  - cambio de proveedor / pidio esperar / no contesto y luego aparece una factura nueva
                                                            -> "Volvio a comprar" detectado por factura

Uso:  python -m app.herramientas.datos_demo --crear      agrega los seguimientos y facturas "DEMO - ..."
      python -m app.herramientas.datos_demo --telegram   manda a los administradores un EJEMPLO del resumen
                                        diario y de la escalacion (con clientes inventados)
      python -m app.herramientas.datos_demo --borrar     borra todos los seguimientos y facturas "DEMO - ..."
"""

import argparse
import json
import os
from datetime import date, datetime, timedelta

from app import negocio
from app.negocio import resultados as resultados_negocio
from app.telegram import avisos, resumen

PREFIJO = negocio.PREFIJO_DEMO
E, A, C = "DAVLI", "Ana López (demo)", "Carlos Ruiz (demo)"
ESPERAR, VENDIO, PROVEEDOR, NO_CONTESTO = "contactado_esperar", "vendio_de_nuevo", "cambio_proveedor", "no_contesto"

# (dias atras, cliente, codigo, resultado, dias para recordar, nota, usuario)
CASOS = [
    # Volvieron a comprar (con factura)
    (58, "MAQUILADORA DEL BAJIO", "921999", ESPERAR, 20, None, E),
    (52, "MAQUILADORA DEL BAJIO", "921999", VENDIO, None, None, E),
    (55, "PLASTICOS INDUSTRIALES NORTE", "937491", NO_CONTESTO, None, "Llamé dos veces, nadie contestó", A),
    (
        52,
        "PLASTICOS INDUSTRIALES NORTE",
        "937491",
        NO_CONTESTO,
        None,
        "Mandé WhatsApp, sin respuesta",
        A + " (Telegram)",
    ),
    (49, "PLASTICOS INDUSTRIALES NORTE", "937491", VENDIO, None, None, A),
    (41, "EMPAQUES Y ENVASES DEL SUR", "937396Q", VENDIO, None, None, C),
    (35, "FUNDICION SAN MIGUEL", "938283Q", ESPERAR, 10, None, A),
    (25, "FUNDICION SAN MIGUEL", "938283Q", VENDIO, None, None, A),
    (33, "ALIMENTOS PROCESADOS DEL GOLFO", "PR2843Q", VENDIO, None, None, E),
    (22, "QUIMICOS DEL PACIFICO", "937491", VENDIO, None, None, A),
    (15, "LOGISTICA Y ALMACENES CENTRAL", "924452Q", VENDIO, None, None, E),
    # Volvieron a comprar pero SIN factura
    (1, "CERVECERA DEL VALLE", "921999", VENDIO, None, None, A + " (Telegram)"),  # dia 1: prorroga
    (9, "DISTRIBUIDORA ANAHUAC", "926169", VENDIO, None, None, C),  # dia 9: esperando factura
    (20, "COMERCIAL DEL PACIFICO", "924452Q", VENDIO, None, None, E),  # dia 20: vencido, contactar
    # Cambiaron de proveedor
    (47, "HIDRAULICA DEL CENTRO", "926169", PROVEEDOR, None, "Le dieron mejor precio", C),
    (39, "TALLER MECANICO LOPEZ", "927736", NO_CONTESTO, None, "Fui a la empresa y estaba cerrado", C),
    (36, "TALLER MECANICO LOPEZ", "927736", PROVEEDOR, None, "Compró a un distribuidor local", C),
    (31, "CONSTRUCTORA ANDES", "943706Q", PROVEEDOR, None, "Cambió a marca Donaldson", A),
    (18, "MINERA LA ESPERANZA", "937396Q", NO_CONTESTO, None, "Mandé correo, sin respuesta", C),
    (17, "MINERA LA ESPERANZA", "937396Q", PROVEEDOR, None, None, C),
    (2, "TORNILLOS Y HERRAMIENTAS UNION", "943706Q", PROVEEDOR, None, "Cerró el área que usaba ese filtro", E),
    # No contestaron
    (27, "TEXTILES DE OCCIDENTE", "926169", NO_CONTESTO, None, "Llamé, sin respuesta", E + " (Telegram)"),
    (24, "TEXTILES DE OCCIDENTE", "926169", NO_CONTESTO, None, "Segundo intento: llamé y mandé correo", E),
    (6, "IMPRESORA DEL NORTE", "921999", NO_CONTESTO, None, "Llamé, sin respuesta", C),
    (4, "IMPRESORA DEL NORTE", "921999", NO_CONTESTO, None, "Mandé WhatsApp, sin respuesta", C),
    (
        8,
        "FABRICA DE ENVASES ORIENTE",
        "938283Q",
        NO_CONTESTO,
        None,
        "Llamé y mandé WhatsApp; sin respuesta",
        E + " (Telegram)",
    ),
    # Pidieron esperar
    (44, "AUTOPARTES MONTERREY", "924452Q", ESPERAR, 15, None, E + " (Telegram)"),
    (12, "PANIFICADORA LA ROSA", "927736", ESPERAR, 8, None, A),
    (4, "AGROINDUSTRIAS SAN JOSE", "926169", ESPERAR, 14, None, A),
    (3, "HULES Y PLASTICOS DEL BAJIO", "937396Q", ESPERAR, 20, None, E),
    (5, "FABRICA DE ENVASES ORIENTE", "938283Q", ESPERAR, 6, None, E + " (Telegram)"),
    # Terminaron como "perdidos / pendientes" pero despues aparecio una factura nueva en ERP
    (30, "FERRETERIA CENTRAL", "937491", PROVEEDOR, None, "Le dieron mejor precio", C),
    (40, "MOLINOS DEL NORTE", "927736", ESPERAR, 10, None, A),
    (25, "CLINICA SAN RAFAEL", "943706Q", NO_CONTESTO, None, "Llamé tres veces", E),
]

# Facturas inventadas MAS NUEVAS que el ultimo seguimiento (cliente, codigo, dias atras de la factura)
FACTURAS_EXTRA = [
    ("FERRETERIA CENTRAL", "937491", 5),
    ("MOLINOS DEL NORTE", "927736", 20),
    ("CLINICA SAN RAFAEL", "943706Q", 10),
]
SIN_FACTURA = {"CERVECERA DEL VALLE", "DISTRIBUIDORA ANAHUAC", "COMERCIAL DEL PACIFICO"}


def _facturas():
    """{"DEMO - cliente|codigo": fecha_iso}: los que terminaron en 'volvio a comprar' (salvo los que
    deben verse sin factura) tienen una factura 2 dias despues; mas las extra."""
    hoy = datetime.combine(date.today(), datetime.min.time())
    ultimo = {}
    for dias, cliente, codigo, resultado, *_ in CASOS:  # los casos van de lo mas viejo a lo mas nuevo por cliente
        ultimo[(cliente, codigo)] = (dias, resultado)
    facturas = {}
    for (cliente, codigo), (dias, resultado) in ultimo.items():
        if resultado == VENDIO and cliente not in SIN_FACTURA:
            facturas[f"{PREFIJO}{cliente}|{codigo}"] = (hoy - timedelta(days=max(0, dias - 2))).isoformat()
    for cliente, codigo, dias in FACTURAS_EXTRA:
        facturas[f"{PREFIJO}{cliente}|{codigo}"] = (hoy - timedelta(days=dias)).isoformat()
    return facturas


def crear():
    ahora = datetime.now()
    conn = negocio.conectar()
    try:
        ya = conn.execute("SELECT COUNT(*) FROM seguimientos WHERE clave_cliente LIKE ?", (PREFIJO + "%",)).fetchone()[
            0
        ]
        if ya:
            print(f"Ya hay {ya} seguimientos DEMO; corre --borrar antes de crearlos de nuevo.")
            return
        for dias, cliente, codigo, resultado, recordar, nota, usuario in CASOS:
            fecha = (ahora - timedelta(days=dias, hours=dias % 7)).isoformat()
            proximo = (date.today() - timedelta(days=dias) + timedelta(days=recordar)).isoformat() if recordar else None
            conn.execute(
                "INSERT INTO seguimientos (clave_cliente, codigo, resultado, proximo_recordatorio, nota, usuario, fecha) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (PREFIJO + cliente, codigo, resultado, proximo, nota, usuario, fecha),
            )
        conn.commit()
    finally:
        conn.close()
    with open(resultados_negocio.RUTA_COMPRAS_DEMO, "w", encoding="utf-8") as f:
        json.dump(_facturas(), f, ensure_ascii=False)
    print(
        f"Creados {len(CASOS)} seguimientos DEMO y {len(_facturas())} facturas inventadas. "
        "Míralos en la pestaña Resultados. Para quitarlos: --borrar"
    )


def borrar():
    conn = negocio.conectar()
    try:
        n = conn.execute("DELETE FROM seguimientos WHERE clave_cliente LIKE ?", (PREFIJO + "%",)).rowcount
        conn.commit()
    finally:
        conn.close()
    hubo_facturas = os.path.exists(resultados_negocio.RUTA_COMPRAS_DEMO)
    if hubo_facturas:
        os.remove(resultados_negocio.RUTA_COMPRAS_DEMO)
    print(f"Borrados {n} seguimientos DEMO{' y las facturas inventadas' if hubo_facturas else ''}.")


def telegram():
    hoy = date.today()

    def alerta(cliente, codigo, nombre, dias, **extra):
        return {
            "cliente": PREFIJO + cliente,
            "clave_cliente": PREFIJO + cliente,
            "codigo": codigo,
            "nombre_producto": nombre,
            "proximo_contacto": (hoy - timedelta(days=dias)).isoformat(),
            "vencido": dias > 0,
            **extra,
        }

    alertas = [
        alerta("MAQUILADORA DEL BAJIO", "921999", "ELEMENTO FILTRANTE PARA 12AT DE 10 MICRONES", 9),
        alerta("PLASTICOS INDUSTRIALES NORTE", "937491", 'FILTRO DE SUCCIÓN INTERNO DE 1 1/2" NPT', 6),
        alerta(
            "COMERCIAL DEL PACIFICO",
            "924452Q",
            "ELEMENTO FILTRANTE PARA MODUFLOW PLUS",
            1,
            estado="factura_vencida",
            nota_estado=(hoy - timedelta(days=16)).isoformat(),
        ),
        alerta("AUTOPARTES MONTERREY", "924452Q", "ELEMENTO FILTRANTE PARA MODUFLOW PLUS", 0),
        alerta("EMPAQUES Y ENVASES DEL SUR", "937396Q", "ELEMENTO FILTRANTE PARA MODUFLOW PLUS DE 20 MICRONES", -4),
    ]
    cfg = avisos.cargar_config()
    marca = "\U0001f9ea <i>EJEMPLO con clientes inventados; no hay que hacer nada.</i>\n\n"
    textos = [marca + resumen.texto_resumen(alertas, hoy)]
    elegidas = resumen.seleccionar_escalacion(alertas, {}, hoy)
    textos.append(marca + resumen.texto_escalacion(elegidas, hoy))
    ventas = [
        {
            "clave_cliente": PREFIJO + "DISTRIBUIDORA ANAHUAC",
            "codigo": "926169",
            "fecha": (datetime.now() - timedelta(days=9)).isoformat(),
        }
    ]
    textos.append(
        marca
        + resumen.texto_facturas(
            resumen.seleccionar_facturas(ventas, {}, hoy),
            hoy,
            {"926169": "ELEMENTO FILTRANTE PARA 12AT DE 10 MICRONES"},
        )
    )
    chats = resumen.chats_admin(cfg)
    for texto in textos:
        for chat in chats:
            avisos.enviar_mensaje(cfg["token"], chat, texto)
    print(f"Mandados {len(textos)} mensajes de ejemplo a {len(chats)} chat(s) de administradores.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--crear", action="store_true")
    g.add_argument("--telegram", action="store_true")
    g.add_argument("--borrar", action="store_true")
    a = p.parse_args()
    if a.crear:
        crear()
    elif a.telegram:
        telegram()
    else:
        borrar()
