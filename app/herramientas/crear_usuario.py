"""Crea un usuario para entrar al sistema. Uso: python -m app.herramientas.crear_usuario

El primer usuario que se crea queda como administrador; los demas eligen rol.
"""

import getpass
import sys

from app.auth import crear_usuario, listar_usuarios


def main():
    print("=== Crear usuario ===")
    existentes = listar_usuarios()
    primer_usuario = not existentes
    if existentes:
        print(f"Usuarios ya registrados: {', '.join(u['username'] for u in existentes)}")

    nombre = input("Nombre: ").strip()
    username = input("Usuario: ").strip()
    password = getpass.getpass("Contraseña: ")
    password2 = getpass.getpass("Confirma la contraseña: ")

    if not nombre or not username or not password:
        print("Todos los campos son obligatorios.")
        return 1
    if password != password2:
        print("Las contraseñas no coinciden.")
        return 1

    rol = "admin" if primer_usuario else "vendedor"
    if not primer_usuario:
        respuesta = input("¿Este usuario es administrador? (s/n): ").strip().lower()
        rol = "admin" if respuesta == "s" else "vendedor"

    try:
        crear_usuario(nombre, username, password, rol=rol)
    except Exception as e:
        print(f"Error: {e}")
        return 1
    print(f"Usuario '{username}' creado correctamente como '{rol}'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
