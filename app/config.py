"""Rutas del proyecto y de los archivos de configuracion (todo lo que vive en config/).

Un solo lugar para saber donde esta cada archivo; los demas modulos piden su ruta aqui en lugar de
armarla cada uno con os.path.
"""

import os

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR_CONFIG = os.path.join(RAIZ, "config")
ARCHIVO_VERSION = os.path.join(RAIZ, "VERSION")


def ruta_config(nombre):
    """Ruta absoluta de un archivo dentro de config/ (ej. ruta_config("negocio.db"))."""
    return os.path.join(DIR_CONFIG, nombre)
