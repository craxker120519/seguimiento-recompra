"""Textos de Telegram: resumen diario, escalacion, facturas pendientes, ficha de cliente."""

from datetime import date, datetime, timedelta

from app.telegram import avisos, resumen

HOY = date(2026, 9, 25)


def alerta(cliente, dias_vencida, codigo="A", **extra):
    return {
        "cliente": cliente,
        "clave_cliente": cliente.upper(),
        "codigo": codigo,
        "nombre_producto": "ELEMENTO FILTRANTE PARA 12AT DE 10 MICRONES",
        "proximo_contacto": (HOY - timedelta(days=dias_vencida)).isoformat(),
        "vencido": dias_vencida > 0,
        **extra,
    }


def test_resumen_cuenta_ordena_y_escapa():
    alertas = [alerta("Logoplaste", -3), alerta("A & B <RAROS>", 9), alerta("Mayco", 0)]
    t = resumen.texto_resumen(alertas, HOY)
    assert "Vencidos: <b>2</b>" in t and "Por vencer (7 días): <b>1</b>" in t
    assert "A &amp; B &lt;RAROS&gt;" in t and "hace 9 días" in t and "vence hoy" in t
    assert t.index("A &amp; B") < t.index("Mayco") < t.index("Logoplaste")
    assert resumen.texto_resumen([], HOY) is None


def test_resumen_corta_a_15_lineas():
    t = resumen.texto_resumen([alerta(f"Cliente {i}", i) for i in range(20)], HOY)
    assert t.count("<b>Cliente") == 15 and "… y 5 más" in t


def test_dias_del_resumen():
    assert resumen.hay_resumen_hoy({}, date(2026, 9, 26))  # sabado
    assert not resumen.hay_resumen_hoy({}, date(2026, 9, 27))  # domingo
    assert not resumen.hay_resumen_hoy({"resumen_diario": False}, HOY)
    assert resumen.hay_resumen_hoy({"resumen_dias": [6]}, date(2026, 9, 27))


def test_escalacion_a_los_5_dias_y_se_repite_cada_7():
    alertas = [alerta("A", 9), alerta("B", 5), alerta("C", 4)]
    el = resumen.seleccionar_escalacion(alertas, {}, HOY)
    assert [a["cliente"] for a in el] == ["A", "B"]
    resumen.marcar_escaladas(el, HOY)
    estado = resumen.estado_escalacion()
    # a los 6 dias A y B (ya avisados) no se repiten; C recien cumple su tiempo
    assert [a["cliente"] for a in resumen.seleccionar_escalacion(alertas, estado, HOY + timedelta(days=6))] == ["C"]
    assert len(resumen.seleccionar_escalacion(alertas, estado, HOY + timedelta(days=7))) == 3
    assert "Ya pasó su fecha" in resumen.texto_escalacion(el, HOY)


def test_alerta_de_factura_vencida_lo_dice_en_todos_los_textos():
    a = alerta("C", 1, estado="factura_vencida", nota_estado="2026-09-09")
    assert "sigue sin factura" in avisos._texto(a)
    assert "sin factura" in resumen._linea(a, HOY)


def _venta(cliente, dias):
    return {
        "clave_cliente": cliente,
        "codigo": "A",
        "fecha": (datetime(2026, 9, 25) - timedelta(days=dias)).isoformat(),
    }


def test_facturas_pendientes_semana_de_prorroga_y_tope_de_15():
    ventas = [_venta("D3", 3), _venta("D8", 8), _venta("D14", 14), _venta("D16", 16), _venta("FACTURADO", 9)]
    compras = {("FACTURADO", "A"): "2026-09-25T00:00:00"}
    pend = resumen.facturas_pendientes(ventas, compras)
    assert {v["clave_cliente"] for v in pend} == {"D3", "D8", "D14", "D16"}
    el = resumen.seleccionar_facturas(pend, {}, HOY)
    assert [v["clave_cliente"] for v in el] == ["D14", "D8"]  # D3: prorroga; D16: ya es alerta vencida
    t = resumen.texto_facturas(el, HOY, {"A": "FILTRO <A>"})
    assert "pasa a vencido en 1 día" in t and "pasa a vencido en 7 días" in t and "FILTRO &lt;A&gt;" in t


def test_facturas_pendientes_se_avisan_cada_semana():
    pend = [_venta("D7", 7)]  # hoy cumple su semana; a los 7 dias mas lleva 14 (<15)
    resumen.marcar_facturas_avisadas(pend, pend, HOY)
    estado = resumen.estado_facturas()
    assert resumen.seleccionar_facturas(pend, estado, HOY + timedelta(days=3)) == []
    assert resumen.seleccionar_facturas(pend, estado, HOY + timedelta(days=7)) == pend
    resumen.marcar_facturas_avisadas([], [], HOY)  # ya no esta pendiente: se olvida
    assert resumen.estado_facturas() == {}


def test_texto_de_estado_para_telegram():
    t = resumen.texto_estado
    assert "Contactar ya" in t("normal", "2026-09-20", None, HOY)
    assert "Vence el 28 sep" in t("normal", "2026-09-28", None, HOY)
    assert "Próximo contacto" in t("normal", "2026-12-01", None, HOY)
    assert "falta vida útil" in t("normal", None, None, HOY)
    assert "esperando factura" in t("esperando_factura", "2026-10-10", "2026-09-25", HOY)
    assert "contactar ya" in t("factura_vencida", "2026-09-20", "2026-09-05", HOY)
    assert "No aplica: cerró" in t("descartado", None, "cerró", HOY)
    assert "reintentar" in t("reintentar", "2026-09-28", "2026-09-25", HOY)


def test_ficha_de_cliente():
    datos = {
        "cliente": "KIPP & CO",
        "productos": [
            {
                "codigo": "921999",
                "nombre": "FILTRO",
                "estado": "normal",
                "nota_estado": None,
                "compras": [{"fecha": "2026-07-29T00:00:00", "proximo_contacto": "2026-09-20"}],
            }
        ],
    }
    t = resumen.texto_cliente(datos, HOY)
    assert "KIPP &amp; CO" in t and "921999" in t and "29 jul" in t and "Contactar ya" in t
