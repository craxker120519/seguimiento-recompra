"""Bot de Telegram: botones de un aviso, notas, "No aplica" y comandos /hoy y /cliente.
Se simulan las llamadas a Telegram y a ERP: ninguna prueba manda mensajes reales."""

import pytest

from app import negocio
from app.jobs import bot_telegram as bot
from app.telegram import avisos

CHAT = "111"


@pytest.fixture
def tg(monkeypatch):
    """Registra todo lo que el bot le manda a Telegram."""
    salida = {"mensajes": [], "ediciones": [], "callbacks": []}
    monkeypatch.setattr(
        bot,
        "_mandar_mensaje",
        lambda token, chat, texto, teclado=None: salida["mensajes"].append((chat, texto, teclado)),
    )
    monkeypatch.setattr(
        bot,
        "_editar_mensaje",
        lambda token, chat, mid, texto, teclado=None: salida["ediciones"].append((texto, teclado)),
    )
    monkeypatch.setattr(bot, "_responder_callback", lambda token, cid, texto=None: salida["callbacks"].append(texto))
    monkeypatch.setattr(bot, "_api", lambda *a, **k: None)
    negocio.agregar_chat_telegram(CHAT, "Ana Lopez")
    monkeypatch.setattr(avisos, "cargar_config", lambda: {"token": "t", "chat_ids": []})
    return salida


def nuevo_aviso(cliente="KIPP", codigo="A"):
    return negocio.registrar_alerta_telegram(cliente, codigo, CHAT, 10, "<b>KIPP</b>\n   A — FILTRO")


def toca(accion, alerta_id):
    bot._procesar_callback(
        "t", {"id": "cb", "data": f"{accion}|{alerta_id}", "from": {"first_name": "Ana"}, "message": {"text": "x"}}
    )


def escribe(texto, chat=CHAT):
    bot._procesar_mensaje_texto("t", {"chat": {"id": chat}, "text": texto, "from": {"first_name": "Ana"}})


def ultimo(cliente="KIPP", codigo="A"):
    return negocio.ultimo_seguimiento(cliente, codigo)


def test_botones_simples(tg):
    toca("vendio", nuevo_aviso())
    s = ultimo()
    assert s["resultado"] == "vendio_de_nuevo" and s["usuario"] == "Ana Lopez (Telegram)"
    assert "Registrado: Volvió a comprar" in tg["ediciones"][-1][0] and "KIPP" in tg["ediciones"][-1][0]


def test_un_aviso_ya_registrado_no_se_registra_dos_veces(tg):
    a = nuevo_aviso()
    toca("vendio", a)
    toca("proveedor", a)
    assert tg["callbacks"][-1] == "Ya se había registrado."
    assert ultimo()["resultado"] == "vendio_de_nuevo"


def test_pidio_esperar_pide_fecha_valida(tg):
    a = nuevo_aviso()
    toca("esperar", a)
    escribe("mañana")
    assert "Fecha no válida" in tg["mensajes"][-1][1] and ultimo() is None
    escribe("15/10/2026")
    s = ultimo()
    assert s["resultado"] == "contactado_esperar" and s["proximo_recordatorio"] == "2026-10-15"


def test_no_contesto_con_notas_rapidas_y_texto(tg):
    a = nuevo_aviso()
    toca("no_contesto", a)
    assert ultimo()["resultado"] == "no_contesto" and "reintentar" in tg["ediciones"][-1][0]
    toca("nc_llamada", a)
    toca("nc_correo", a)
    toca("nc_otra", a)
    escribe("fui a la empresa y estaba cerrado")
    assert ultimo()["nota"] == "Llamé, sin respuesta · Mandé correo, sin respuesta · fui a la empresa y estaba cerrado"
    toca("nc_listo", a)
    assert tg["ediciones"][-1][1] == {"inline_keyboard": []}


def test_las_notas_solo_se_pegan_si_sigue_en_no_contesto(tg):
    a = nuevo_aviso()
    toca("no_contesto", a)
    negocio.registrar_seguimiento("KIPP", "A", "vendio_de_nuevo", None, None, "web")
    toca("nc_llamada", a)
    assert "ya no está" in tg["callbacks"][-1] and ultimo()["nota"] is None


def test_cambio_de_proveedor_escapa_el_motivo(tg):
    a = nuevo_aviso()
    toca("proveedor", a)
    escribe("le dieron <mejor> precio & entrega")
    assert ultimo()["nota"] == "le dieron <mejor> precio & entrega"
    assert "&lt;mejor&gt;" in tg["ediciones"][-1][0]


def test_no_aplica_pide_motivo_y_lo_registra(tg):
    a = nuevo_aviso()
    toca("no_aplica", a)
    assert "No aplica" in tg["ediciones"][-1][0] and ultimo() is None
    escribe("ok")  # demasiado corto
    assert ultimo() is None and "motivo" in tg["mensajes"][-1][1]
    escribe("cerró la empresa")
    s = ultimo()
    assert s["resultado"] == "no_aplica" and s["nota"] == "cerró la empresa"
    assert "Registrado: No aplica" in tg["ediciones"][-1][0]
    assert negocio.resolver_estado("KIPP", "A", "2026-01-01T00:00:00", 4, 1.0, 2)["estado"] == "descartado"


def test_el_aviso_trae_el_boton_no_aplica():
    botones = [b["text"] for fila in avisos._teclado(7)["inline_keyboard"] for b in fila]
    assert "No aplica (descartar)" in botones and len(botones) == 5


# ---- comandos ----


def test_un_chat_no_registrado_no_puede_consultar(tg):
    escribe("/hoy", chat="999")
    escribe("/cliente kipp", chat="999")
    assert all("no está dado de alta" in m[1] for m in tg["mensajes"]) and len(tg["mensajes"]) == 2


def test_ayuda_y_comandos_con_arroba(tg):
    escribe("/ayuda")
    escribe("/hoy@filtros_demo_bot", chat="999")
    assert "/hoy" in tg["mensajes"][0][1] and "no está dado de alta" in tg["mensajes"][1][1]


def test_hoy_lista_lo_que_toca_y_cuenta_las_ventas_esperando_factura(tg, monkeypatch):
    alertas = [
        {
            "cliente": "KIPP",
            "clave_cliente": "KIPP",
            "codigo": "A",
            "nombre_producto": "FILTRO",
            "proximo_contacto": "2026-01-01",
            "vencido": True,
            "estado": "normal",
            "nota_estado": None,
        },
        {
            "cliente": "LOGO",
            "clave_cliente": "LOGO",
            "codigo": "A",
            "nombre_producto": "FILTRO",
            "proximo_contacto": "2099-01-01",
            "vencido": False,
            "estado": "esperando_factura",
            "nota_estado": "2026-09-20",
        },
    ]
    monkeypatch.setattr(bot, "alertas_recontacto", lambda codigos, incluir_esperando_factura=False: alertas)
    monkeypatch.setattr(bot, "codigos_filtro", lambda: ["A"])
    escribe("/hoy")
    texto = tg["mensajes"][-1][1]
    assert "KIPP" in texto and "LOGO" not in texto and "1 venta registrada esperando factura" in texto


def test_hoy_sin_pendientes_y_con_erp_caido(tg, monkeypatch):
    monkeypatch.setattr(bot, "codigos_filtro", lambda: ["A"])
    monkeypatch.setattr(bot, "alertas_recontacto", lambda codigos, incluir_esperando_factura=False: [])
    escribe("/hoy")
    assert "No hay nadie por contactar" in tg["mensajes"][-1][1]

    def falla(codigos, incluir_esperando_factura=False):
        raise RuntimeError("sin conexion")

    monkeypatch.setattr(bot, "alertas_recontacto", falla)
    escribe("/hoy")
    assert "No pude consultar ERP" in tg["mensajes"][-1][1]


def _ficha(nombre="KIPP AUTOMOTIVE"):
    return {
        "cliente": nombre,
        "productos": [
            {
                "codigo": "A",
                "nombre": "FILTRO",
                "estado": "normal",
                "nota_estado": None,
                "compras": [{"fecha": "2026-07-29T00:00:00", "proximo_contacto": "2026-09-20"}],
            }
        ],
    }


def test_cliente_con_un_resultado_muestra_la_ficha(tg, monkeypatch):
    monkeypatch.setattr(bot, "codigos_filtro", lambda: ["A"])
    monkeypatch.setattr(
        bot, "buscar_clientes", lambda q, codigos: [{"nombre": "KIPP AUTOMOTIVE", "legacy_id": 1, "actual_id": None}]
    )
    monkeypatch.setattr(bot, "timeline_cliente", lambda codigos, legacy_id=None, actual_id=None: _ficha())
    escribe("/cliente kipp")
    assert "KIPP AUTOMOTIVE" in tg["mensajes"][-1][1] and "Contactar ya" in tg["mensajes"][-1][1]


def test_cliente_con_varios_resultados_ofrece_botones_y_luego_la_ficha(tg, monkeypatch):
    monkeypatch.setattr(bot, "codigos_filtro", lambda: ["A"])
    monkeypatch.setattr(
        bot,
        "buscar_clientes",
        lambda q, codigos: [
            {"nombre": "KIPP UNO", "legacy_id": 1, "actual_id": None},
            {"nombre": "KIPP DOS", "legacy_id": None, "actual_id": 7},
        ],
    )
    pedidos = []
    monkeypatch.setattr(
        bot,
        "timeline_cliente",
        lambda codigos, legacy_id=None, actual_id=None: pedidos.append((legacy_id, actual_id)) or _ficha("KIPP DOS"),
    )
    escribe("/cliente kipp")
    teclado = tg["mensajes"][-1][2]["inline_keyboard"]
    assert [f[0]["text"] for f in teclado] == ["KIPP UNO", "KIPP DOS"] and teclado[1][0]["callback_data"] == "cli||7"
    bot._procesar_callback("t", {"id": "cb", "data": "cli||7", "message": {"chat": {"id": CHAT}}})
    assert pedidos == [(None, 7)] and "KIPP DOS" in tg["mensajes"][-1][1]


def test_los_botones_de_cliente_tambien_exigen_chat_registrado(tg, monkeypatch):
    llamadas = []
    monkeypatch.setattr(bot, "timeline_cliente", lambda *a, **k: llamadas.append(1))
    bot._procesar_callback("t", {"id": "cb", "data": "cli|1|", "message": {"chat": {"id": "999"}}})
    assert llamadas == [] and tg["callbacks"][-1] == "Este chat no está autorizado."


def test_cliente_sin_texto_o_sin_resultados(tg, monkeypatch):
    monkeypatch.setattr(bot, "codigos_filtro", lambda: ["A"])
    monkeypatch.setattr(bot, "buscar_clientes", lambda q, codigos: [])
    escribe("/cliente")
    assert "Escribe /cliente" in tg["mensajes"][-1][1]
    escribe("/cliente zzz <x>")
    assert "No encontré" in tg["mensajes"][-1][1] and "&lt;x&gt;" in tg["mensajes"][-1][1]
