import pytest

from app import auth


@pytest.mark.parametrize(
    "password, motivo",
    [
        ("corta1", "al menos 10"),
        ("1234567890", "solo números"),
        ("aaaaaaaaaaaa", "repetitiva"),
        ("miusuario123", "igual al usuario"),
    ],
)
def test_contrasenas_debiles_se_rechazan(password, motivo):
    assert motivo in auth.validar_password(password, "miusuario123")


@pytest.mark.parametrize("password", ["MiClaveSegura9", "Segura#2026ok", "una frase larga sirve"])
def test_contrasenas_buenas_pasan(password):
    assert auth.validar_password(password, "usuario") is None


def test_crear_usuario_exige_el_minimo():
    with pytest.raises(ValueError):
        auth.crear_usuario("Ana", "ana", "123456")
    auth.crear_usuario("Ana", "ana", "ClaveMuySegura1")
    assert auth.verificar_usuario("ana", "ClaveMuySegura1")


def test_cambiar_y_establecer_password_exigen_el_minimo():
    auth.crear_usuario("Ana", "ana", "ClaveMuySegura1")
    with pytest.raises(ValueError):
        auth.cambiar_password("ana", "ClaveMuySegura1", "123456")
    with pytest.raises(ValueError):
        auth.establecer_password("ana", "123456")
    assert auth.cambiar_password("ana", "ClaveMuySegura1", "OtraClaveSegura2")
    assert auth.cambiar_password("ana", "incorrecta-larga", "OtraClaveSegura3") is False
    assert auth.verificar_usuario("ana", "OtraClaveSegura2")
