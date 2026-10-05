"""resolver_estado: como cada seguimiento cambia el estado de un cliente+producto."""

from datetime import date, timedelta

import pytest

from app import negocio
from tests.conftest import iso

COMPRA_VIEJA = "2026-01-01T00:00:00"


def estado(cliente="C", codigo="A", compra=COMPRA_VIEJA, unidades=4, meses=1.0, maquinas=2):
    return negocio.resolver_estado(cliente, codigo, compra, unidades, meses, maquinas)


def test_calculo_de_proximo_contacto():
    # 4 filtros / 2 maquinas * 1 mes = 2 meses = round(2 * 30.44) dias
    assert negocio.calcular_proximo_contacto("2026-09-25T00:00:00", 4, 1.0, 2) == "2026-11-25"
    assert negocio.calcular_proximo_contacto("2026-09-25T00:00:00", 4, None, 2) is None
    assert negocio.calcular_proximo_contacto("2026-09-25T00:00:00", 4, 1.0, None) is None


def test_sin_seguimiento_es_normal():
    r = estado()
    assert r["estado"] == "normal" and r["proximo_contacto"] == "2026-03-03"


def test_pidio_esperar(seg):
    seg("C", "contactado_esperar", 1, recordar="2026-10-30")
    assert estado() == {"proximo_contacto": "2026-10-30", "estado": "pendiente", "nota": None}


def test_cambio_de_proveedor_e_inactivo(seg):
    seg("C", "cambio_proveedor", 1, nota="mas barato")
    r = estado()
    assert r["estado"] == "inactivo" and r["nota"] == "mas barato" and r["proximo_contacto"] is None


def test_no_contesto_reintenta_a_los_3_dias(seg):
    seg("C", "no_contesto", 1)
    r = estado()
    assert r["estado"] == "reintentar"
    assert r["proximo_contacto"] == (date.today() - timedelta(days=1) + timedelta(days=3)).isoformat()


def test_no_aplica_descarta_sin_fecha(seg):
    seg("C", "no_aplica", 1, nota="cerro la empresa")
    r = estado()
    assert r == {"proximo_contacto": None, "estado": "descartado", "nota": "cerro la empresa"}


@pytest.mark.parametrize(
    "dias, esperado",
    [
        (0, "esperando_factura"),
        (7, "esperando_factura"),
        (14, "esperando_factura"),
        (15, "factura_vencida"),
        (20, "factura_vencida"),
    ],
)
def test_ciclo_de_volvio_a_comprar_sin_factura(seg, dias, esperado):
    seg("C", "vendio_de_nuevo", dias)
    r = estado()
    assert r["estado"] == esperado
    assert r["proximo_contacto"] == (date.today() - timedelta(days=dias) + timedelta(days=15)).isoformat()
    assert r["nota"] == (date.today() - timedelta(days=dias)).isoformat()


def test_una_factura_mas_nueva_ignora_el_seguimiento(seg):
    seg("C", "cambio_proveedor", 10)
    r = estado(compra=iso(2))  # factura de hace 2 dias, posterior al seguimiento
    assert r["estado"] == "normal"
    assert r["proximo_contacto"] == (date.today() - timedelta(days=2) + timedelta(days=round(2 * 30.44))).isoformat()


def test_un_seguimiento_nuevo_reinicia_el_ciclo(seg):
    seg("C", "vendio_de_nuevo", 20)
    assert estado()["estado"] == "factura_vencida"
    seg("C", "vendio_de_nuevo", 0)
    r = estado()
    assert r["estado"] == "esperando_factura"
    assert r["proximo_contacto"] == (date.today() + timedelta(days=15)).isoformat()


def test_notas_de_no_contesto_se_acumulan(seg):
    seg("C", "no_contesto", 0)
    negocio.agregar_nota_ultimo_seguimiento("C", "A", "Llamé, sin respuesta")
    negocio.agregar_nota_ultimo_seguimiento("C", "A", "Mandé correo, sin respuesta")
    assert negocio.ultimo_seguimiento("C", "A")["nota"] == "Llamé, sin respuesta · Mandé correo, sin respuesta"
