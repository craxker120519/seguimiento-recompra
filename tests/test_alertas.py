"""alertas_recontacto con las consultas a ERP simuladas."""

from datetime import date

import pytest

from app import negocio
from app.erp import compras as db


@pytest.fixture
def erp(monkeypatch):
    """Simula las dos bases de ERP: filas = [{"cliente", "codigo", "fecha", "unidades"}]."""
    filas = []
    monkeypatch.setattr(db, "_ultima_compra_por_cliente_legacy", lambda codigos: filas)
    monkeypatch.setattr(db, "_ultima_compra_por_cliente_actual", lambda codigos: [])
    monkeypatch.setattr(db, "catalogo_filtros", lambda codigos: [{"codigo": "A", "nombre": "FILTRO A"}])
    return filas


def alta(erp, cliente, unidades=1.0, fecha="2026-01-01T00:00:00"):
    negocio.set_vida_util("A", 1.0)
    negocio.set_maquinas(cliente, "A", 1)
    erp.append({"cliente": cliente, "codigo": "A", "fecha": fecha, "unidades": unidades})


def test_solo_regresa_lo_vencido_o_por_vencer(erp):
    alta(erp, "VENCIDO")  # compro en enero: ya vencio
    alta(erp, "LEJANO", fecha=date.today().isoformat() + "T00:00:00")  # proximo contacto en ~1 mes
    assert [a["cliente"] for a in db.alertas_recontacto(["A"])] == ["VENCIDO"]


def test_sin_vida_util_o_maquinas_no_hay_alerta(erp):
    erp.append({"cliente": "SIN DATOS", "codigo": "A", "fecha": "2026-01-01T00:00:00", "unidades": 1.0})
    assert db.alertas_recontacto(["A"]) == []


@pytest.mark.parametrize("resultado", ["cambio_proveedor", "no_aplica"])
def test_cambio_de_proveedor_y_no_aplica_no_alertan(erp, seg, resultado):
    alta(erp, "C")
    seg("C", resultado, 1, nota="motivo")
    assert db.alertas_recontacto(["A"]) == []
    assert db.alertas_recontacto(["A"], incluir_esperando_factura=True) == []


def test_volvio_a_comprar_sin_factura_sigue_el_ciclo(erp, seg):
    for cliente, dias in {"DIA 3": 3, "DIA 8": 8, "DIA 14": 14, "DIA 16": 16}.items():
        alta(erp, cliente)
        seg(cliente, "vendio_de_nuevo", dias)
    contactar = {a["cliente"]: a for a in db.alertas_recontacto(["A"])}
    assert set(contactar) == {"DIA 16"} and contactar["DIA 16"]["estado"] == "factura_vencida"
    todas = {a["cliente"]: a for a in db.alertas_recontacto(["A"], incluir_esperando_factura=True)}
    assert set(todas) == {"DIA 8", "DIA 14", "DIA 16"}  # el dia 3 sigue en la semana de prorroga
    assert todas["DIA 8"]["estado"] == "esperando_factura" and not todas["DIA 8"]["vencido"]


def test_una_factura_nueva_cancela_el_ciclo(erp, seg):
    alta(erp, "C", fecha="2026-09-01T00:00:00")
    seg("C", "vendio_de_nuevo", 20)
    erp[0]["fecha"] = date.today().isoformat() + "T00:00:00"  # llega la factura
    assert db.alertas_recontacto(["A"], incluir_esperando_factura=True) == []  # ciclo nuevo: falta ~1 mes
