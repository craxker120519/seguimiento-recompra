# Seguimiento de recompra de filtros

Sistema que sigue las ventas de filtros industriales registradas en el ERP de
la empresa, calcula **cuándo le toca volver a comprar a cada cliente** (según la
vida útil del filtro y las máquinas del cliente) y avisa al equipo de ventas por
Telegram. Todo lo que el equipo habla con el cliente se registra como
*seguimiento*.

## Funcionalidades

- **Alertas de recompra** por cliente y filtro, con aviso a una semana.
- **Seguimiento de contactos** con estados del caso.
- **Bot de Telegram** con botones para registrar seguimientos y comandos `/hoy`, `/cliente`, `/ayuda`; resumen diario y escalación.
- **Catálogo** de filtros vigilados, vida útil y máquinas por cliente; exportación a Excel.
- **Usuarios con roles**, límite de intentos de login e invitaciones a Telegram por enlace.
- **Procesos automáticos:** alertas diarias, salud del sistema, latido y respaldo.
- Lee del ERP (SQL Server) **solo en modo lectura**; lo que se captura vive en su propia base SQLite.

## Estructura

```
app/
  config.py      rutas de config/
  auth.py        usuarios y contraseñas
  server.py      punto de entrada (gunicorn app.server:app)
  web/           la página y su API, un archivo por tema
  negocio/       base propia (SQLite): catálogo, estados, seguimientos, resultados, Telegram, seguridad
  erp/           lectura del ERP (SQL Server, solo lectura): catálogo, productos, clientes, compras
  telegram/      avisos con botones y resumen diario
  jobs/          procesos automáticos: alertas_diarias, bot_telegram, salud, latido, respaldo
  herramientas/  administración: crear_usuario, crear_invitacion_telegram, datos_demo, etc.
  static/        páginas HTML, CSS y JS (un archivo por pestaña)
data/            Excel de ejemplo para sembrar el catálogo la primera vez
tests/           pruebas automáticas
docs/            arquitectura
```

## Ejecutarlo en tu máquina

Requiere Python 3.12 o superior y el *ODBC Driver 18 for SQL Server*.

```bash
pip install -r requirements.txt
cp config/db_config.example.json config/db_config.json          # datos de conexión al ERP
cp config/telegram_config.example.json config/telegram_config.json
python -m app.herramientas.crear_usuario                         # primer usuario (administrador)
python -m app.server
```

El bot y los envíos diarios se lanzan con `python -m app.jobs.bot_telegram` y
`python -m app.jobs.alertas_diarias` (`--ver` muestra los mensajes sin enviarlos).

## Pruebas

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q
python -m ruff check .
```

Las pruebas no usan la base real, ni el ERP, ni Telegram: todo va simulado
(ver `tests/conftest.py`). En GitHub corren solas en cada subida
(`.github/workflows/pruebas.yml`).

Ver [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md) para el flujo de datos y el modelo de estados.

## Licencia

Código publicado **solo para consulta** (portafolio). Todos los derechos reservados.
Antes de usar, copiar o modificar cualquier parte de este proyecto debes
**contactar al autor y obtener su autorización por escrito**:
[github.com/craxker120519](https://github.com/craxker120519). Ver [`LICENSE`](./LICENSE).
