"""Punto de entrada de la pagina web: `gunicorn app.server:app` (Caddy hace de proxy hacia 127.0.0.1:5057).

Toda la logica esta en el paquete app/web/ (un archivo por tema).
"""

from app.web import crear_app

app = crear_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5057, debug=False)
