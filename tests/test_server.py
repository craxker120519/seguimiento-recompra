"""Rutas de seguimiento y de usuarios."""

import pytest

from app import auth, negocio, server


@pytest.fixture
def web():
    c = server.app.test_client()
    with c.session_transaction() as s:
        s.update(usuario_id=1, usuario_rol="admin", usuario_nombre="Ana Lopez", usuario_username="ana")
    return c


def post(web, **campos):
    base = {"clave_cliente": "KIPP", "codigo": "A", "resultado": "vendio_de_nuevo"}
    return web.post("/api/seguimiento", json={**base, **campos})


def test_registrar_seguimientos_validos(web):
    assert post(web).status_code == 200
    assert negocio.ultimo_seguimiento("KIPP", "A")["resultado"] == "vendio_de_nuevo"
    assert negocio.ultimo_seguimiento("KIPP", "A")["usuario"] == "Ana Lopez"
    assert post(web, resultado="contactado_esperar", proximo_recordatorio="2026-12-01").status_code == 200


@pytest.mark.parametrize(
    "campos",
    [
        {"resultado": "inventado"},
        {"resultado": "contactado_esperar"},  # falta la fecha
        {"resultado": "no_aplica"},  # falta el motivo
        {"resultado": "no_aplica", "nota": "  "},
        {"codigo": ""},
    ],
)
def test_seguimientos_invalidos(web, campos):
    assert post(web, **campos).status_code == 400
    assert negocio.ultimo_seguimiento("KIPP", "A") is None


def test_no_aplica_a_un_producto_o_a_todos_los_del_cliente(web):
    assert post(web, resultado="no_aplica", nota="ya no usa el filtro").status_code == 200
    assert negocio.ultimo_seguimiento("KIPP", "B") is None
    r = post(web, resultado="no_aplica", nota="cerro la empresa", codigos=["A", "B", "C"])
    assert r.status_code == 200 and r.get_json()["registrados"] == 3
    for codigo in "ABC":
        assert negocio.ultimo_seguimiento("KIPP", codigo)["nota"] == "cerro la empresa"


def test_codigos_solo_aplican_a_no_aplica(web):
    post(web, resultado="vendio_de_nuevo", codigos=["B"])
    assert negocio.ultimo_seguimiento("KIPP", "B") is None


def test_historial_del_seguimiento(web):
    post(web, resultado="no_contesto", nota="llame")
    h = web.get("/api/seguimiento?clave_cliente=KIPP&codigo=A").get_json()
    assert h[0]["resultado"] == "no_contesto" and h[0]["nota"] == "llame"


def test_contrasenas_debiles_se_rechazan_en_la_web(web):
    assert (
        web.post("/api/usuarios", json={"nombre": "Ana", "username": "nueva", "password": "123456"}).status_code == 400
    )
    assert (
        web.post(
            "/api/usuarios", json={"nombre": "Ana", "username": "nueva", "password": "ClaveMuySegura1"}
        ).status_code
        == 200
    )
    uid = next(u["id"] for u in auth.listar_usuarios() if u["username"] == "nueva")
    r = web.post(f"/api/usuarios/{uid}/password", json={"password_nueva": "1234567890"})
    assert r.status_code == 400 and "solo números" in r.get_json()["error"]
    assert web.post(f"/api/usuarios/{uid}/password", json={"password_nueva": "OtraClaveSegura2"}).status_code == 200
    r = web.post("/api/cambiar-password", json={"password_actual": "x", "password_nueva": "corta"})
    assert r.status_code == 400


def test_solo_el_admin_crea_usuarios_y_cambia_contrasenas(web):
    with web.session_transaction() as s:
        s["usuario_rol"] = "vendedor"
    assert (
        web.post("/api/usuarios", json={"nombre": "X", "username": "x", "password": "ClaveMuySegura1"}).status_code
        == 403
    )
    assert web.post("/api/usuarios/1/password", json={"password_nueva": "ClaveMuySegura1"}).status_code == 403
