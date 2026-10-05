"""Genera un link de invitacion para que alguien nuevo se de de alta en los avisos de Telegram
sin tener que buscar su chat_id a mano.

Uso: python -m app.herramientas.crear_invitacion_telegram
(Tambien se puede hacer desde la pagina: Usuarios -> Avisos de Telegram.)
"""

import sys

from app import negocio
from app.web.usuarios import BOT_TELEGRAM_USUARIO


def main():
    print("=== Crear invitacion de Telegram ===")
    nombre = input("Nombre de la persona: ").strip()
    if not nombre:
        print("El nombre es obligatorio.")
        return 1

    token = negocio.crear_invitacion_telegram(nombre)
    print(f"Listo. Mandale este link a {nombre}:")
    print(f"https://t.me/{BOT_TELEGRAM_USUARIO}?start={token}")
    print("En cuanto lo abra y le de 'Iniciar', queda dado de alta automaticamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
