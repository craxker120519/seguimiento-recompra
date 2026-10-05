"""Tareas programadas: envio diario, latido y monitor de salud."""

import os
from datetime import datetime, timedelta

import pytest

from app.jobs import alertas_diarias as ta
from app.jobs import latido, salud
from app.telegram import avisos

# ---- envio diario (telegram_alertas.py) ----


@pytest.fixture
def envio(monkeypatch):
    enviados = []
    monkeypatch.setattr(avisos, "cargar_config", lambda: {"token": "t", "chat_ids": ["c1"]})
    monkeypatch.setattr(
        avisos, "enviar_mensaje", lambda token, chat, texto, teclado=None: enviados.append((chat, texto))
    )
    monkeypatch.setattr(ta, "alertas_recontacto", lambda codigos: [])
    monkeypatch.setattr(ta, "codigos_filtro", lambda: ["A"])
    monkeypatch.setattr(ta, "catalogo_filtros", lambda codigos: [{"codigo": "A", "nombre": "FILTRO A"}])
    monkeypatch.setattr(ta, "ultimas_compras", lambda codigos: {})
    monkeypatch.setattr("sys.argv", ["telegram_alertas.py"])
    return enviados


def test_si_una_parte_falla_las_otras_corren_y_el_proceso_termina_con_error(envio, monkeypatch):
    llamadas = []

    def rota(cfg, chats, alertas, hoy):
        llamadas.append("alertas")
        raise RuntimeError("falla simulada")

    monkeypatch.setattr(ta, "_parte_alertas", rota)
    monkeypatch.setattr(ta, "_parte_facturas", lambda cfg, chats, hoy: llamadas.append("facturas"))
    monkeypatch.setattr(ta, "_parte_escalacion", lambda cfg, alertas, hoy: llamadas.append("escalacion"))
    assert ta.main() == 1
    assert llamadas == ["alertas", "facturas", "escalacion"]


def test_sin_fallas_termina_bien(envio, monkeypatch):
    monkeypatch.setattr(ta, "_parte_alertas", lambda *a: None)
    monkeypatch.setattr(ta, "_parte_facturas", lambda *a: None)
    monkeypatch.setattr(ta, "_parte_escalacion", lambda *a: None)
    assert ta.main() == 0


def test_un_dia_completo_manda_facturas_pendientes_una_sola_vez(envio, seg):
    seg("KIPP", "vendio_de_nuevo", 8)
    assert ta.main() == 0
    textos = [t for _, t in envio]
    assert len(textos) == 1 and "aún no hay factura" in textos[0] and "KIPP" in textos[0]
    envio.clear()
    assert ta.main() == 0
    assert envio == []  # ya se aviso hoy


def test_si_telegram_no_recibe_las_facturas_se_reintenta(envio, seg, monkeypatch):
    import requests

    seg("KIPP", "vendio_de_nuevo", 8)

    def cae(token, chat, texto, teclado=None):
        raise requests.ConnectionError("sin internet")

    monkeypatch.setattr(avisos, "enviar_mensaje", cae)
    assert ta.main() == 0  # no rompe el proceso...
    monkeypatch.setattr(avisos, "enviar_mensaje", lambda token, chat, texto, teclado=None: envio.append((chat, texto)))
    assert ta.main() == 0
    assert len(envio) == 1  # ...y al dia siguiente si se avisa


def test_los_clientes_demo_nunca_avisan(envio, seg):
    seg("DEMO - KIPP", "vendio_de_nuevo", 8)
    assert ta.main() == 0 and envio == []


# ---- latido ----


def test_el_latido_avisa_si_el_monitor_lleva_mas_de_10_minutos_parado(tmp_path, monkeypatch):
    archivo = tmp_path / "salud_estado.json"
    monkeypatch.setattr(latido, "_ESTADO_MONITOR", str(archivo))
    assert latido.monitor_vivo()  # sin archivo: no hay de que alarmarse todavia
    archivo.write_text("{}")
    m = os.path.getmtime(archivo)
    assert latido.monitor_vivo(m + 60)
    assert latido.monitor_vivo(m + 60 * 10)
    assert not latido.monitor_vivo(m + 60 * 11)
    assert round(latido.minutos_sin_monitor(m + 120)) == 2


# ---- monitor de salud ----


def test_el_monitor_confirma_avisa_recuerda_y_da_por_resuelto():
    t0 = datetime(2026, 9, 25, 8, 0)
    problema = ["Servicio caddy está 'failed'"]
    m, estado = salud.evaluar_monitor(problema, {}, t0)
    assert m == []  # la primera vez no avisa (evita falsas alarmas)
    m, estado = salud.evaluar_monitor(problema, estado, t0 + timedelta(minutes=2))
    assert len(m) == 1 and "Problema detectado" in m[0]
    m, estado = salud.evaluar_monitor(problema, estado, t0 + timedelta(minutes=4))
    assert m == []  # ya avisado
    m, estado = salud.evaluar_monitor(problema, estado, t0 + timedelta(hours=7))
    assert len(m) == 1 and "Sigue sin resolverse" in m[0]
    m, estado = salud.evaluar_monitor([], estado, t0 + timedelta(hours=8))
    assert len(m) == 1 and "Resuelto" in m[0]


def test_un_problema_que_cambia_de_numero_es_el_mismo():
    assert salud._clave("El último respaldo tiene 26 horas") == salud._clave("El último respaldo tiene 31 horas")


def test_una_falla_de_un_segundo_no_manda_falsa_alarma(monkeypatch):
    """Al reiniciar la app (deploy) la primera revision falla y la segunda ya responde."""
    respuestas = iter([False, True])
    monkeypatch.setattr(latido, "app_responde", lambda: next(respuestas))
    monkeypatch.setattr(latido, "caddy_responde", lambda: True)
    monkeypatch.setattr(latido, "monitor_vivo", lambda: True)
    monkeypatch.setattr(latido.time, "sleep", lambda s: None)
    assert latido.revisar_con_reintento() == []


def test_una_falla_que_persiste_si_se_avisa(monkeypatch):
    monkeypatch.setattr(latido, "app_responde", lambda: False)
    monkeypatch.setattr(latido, "caddy_responde", lambda: True)
    monkeypatch.setattr(latido, "monitor_vivo", lambda: True)
    esperas = []
    monkeypatch.setattr(latido.time, "sleep", esperas.append)
    assert latido.revisar_con_reintento() == ["la app (gunicorn) no responde"]
    assert esperas == [latido.SEGUNDOS_REINTENTO]
