"""Fixtures compartidas. Ninguna prueba toca la base real ni se conecta a ERP o a Telegram:
cada una trabaja sobre una base SQLite temporal y con las consultas a ERP simuladas."""

from datetime import date, datetime, timedelta

import pytest

from app.negocio import conexion, resultados
from app.telegram import resumen


@pytest.fixture(autouse=True)
def base_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(conexion, "RUTA_DB", str(tmp_path / "negocio.db"))
    monkeypatch.setattr(resultados, "RUTA_COMPRAS_DEMO", str(tmp_path / "demo_compras.json"))
    monkeypatch.setattr(resumen, "_ESTADO_ESCALACION", str(tmp_path / "escalacion.json"))
    monkeypatch.setattr(resumen, "_ESTADO_FACTURAS", str(tmp_path / "facturas.json"))
    return tmp_path


@pytest.fixture
def seg():
    """seg("CLIENTE", "vendio_de_nuevo", dias_atras=8, codigo="A", nota=None, recordar=None)
    inserta un seguimiento con fecha atrasada (registrar_seguimiento siempre usa 'ahora')."""

    def _seg(cliente, resultado, dias_atras=0, codigo="A", nota=None, recordar=None, usuario="Ana (Telegram)"):
        fecha = datetime.combine(date.today() - timedelta(days=dias_atras), datetime.min.time()).replace(hour=11)
        conn = conexion.conectar()
        try:
            conn.execute(
                "INSERT INTO seguimientos (clave_cliente, codigo, resultado, proximo_recordatorio, nota, usuario, fecha) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (cliente, codigo, resultado, recordar, nota, usuario, fecha.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    return _seg


def iso(dias_atras=0):
    """Fecha ISO (medianoche) de hace N dias; negativo = futuro."""
    return datetime.combine(date.today() - timedelta(days=dias_atras), datetime.min.time()).isoformat()
