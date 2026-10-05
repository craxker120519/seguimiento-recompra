"""Avisos de PRUEBA por Telegram (con sus botones) para probar el bot.

Uso:  python -m app.herramientas.enviar_prueba             3 avisos con clientes FICTICIOS: no existen
                                          en el sistema, no cambian el estado de nadie.
      python -m app.herramientas.enviar_prueba --reales    3 avisos sobre alertas REALES pendientes, para
                                          ver como se actualizan en la pagina. Todo lo que
                                          se registre en ellos se deshace con --limpiar.
                                          --cantidad N cambia cuantos (por defecto 3); se
                                          saltan los clientes que ya tuvieron aviso de prueba.
                                          --completar: si no hay suficientes, da de alta vida
                                          util y maquinas de prueba en otros clientes/filtros.
      python -m app.herramientas.enviar_prueba --limpiar   borra los avisos de prueba y DESHACE los
                                          seguimientos registrados a traves de ellos, para
                                          que cada cliente real quede como estaba antes.
"""

import argparse
from datetime import date, datetime, timedelta

from app import negocio
from app.telegram import avisos

PREFIJO = "__prueba_"
NOTA_FICTICIO = "\U0001f9ea aviso de prueba, no es un cliente real"
NOTA_REAL = "\U0001f9ea PRUEBA sobre un cliente REAL: lo que registres se deshace con --limpiar"


def _ficticios():
    hoy = date.today()
    return [
        {
            "clave_cliente": PREFIJO + "1__",
            "cliente": "PRUEBA 1 - CLIENTE DE EJEMPLO, S.A. DE C.V.",
            "codigo": "TEST-001",
            "nombre_producto": "FILTRO DE PRUEBA (ya vencido)",
            "proximo_contacto": (hoy - timedelta(days=12)).isoformat(),
            "vencido": True,
        },
        {
            "clave_cliente": PREFIJO + "2__",
            "cliente": "PRUEBA 2 - MAQUILADORA DEMO",
            "codigo": "TEST-002",
            "nombre_producto": "ELEMENTO DE PRUEBA (vence pronto)",
            "proximo_contacto": (hoy + timedelta(days=3)).isoformat(),
            "vencido": False,
        },
        {
            "clave_cliente": PREFIJO + "3__",
            "cliente": "PRUEBA 3 - A & B <SIMBOLOS> RAROS S.A.",
            "codigo": "TEST-003",
            "nombre_producto": 'FILTRO CON "COMILLAS" & SIMBOLOS',
            "proximo_contacto": (hoy - timedelta(days=1)).isoformat(),
            "vencido": True,
        },
    ]


def _reales(cantidad=3):
    from app.erp import alertas_recontacto
    from app.negocio.filtros import codigos_filtro

    # Se saltan los clientes/productos que ya tienen un aviso de prueba, para probar con otros
    conn = negocio.conectar()
    try:
        usados = {tuple(r) for r in conn.execute("SELECT clave_cliente, codigo FROM alertas_telegram WHERE prueba = 1")}
    finally:
        conn.close()
    nuevas = [a for a in alertas_recontacto(codigos_filtro()) if (a["clave_cliente"], a["codigo"]) not in usados]
    return nuevas[:cantidad]


def _completar(faltan):
    """Si hay menos alertas reales que las pedidas, da de alta vida util (1 producto sin
    configurar) y 1 maquina en `faltan` combinaciones cliente+producto con compra real,
    de modo que su recontacto ya toque. Es informacion de prueba: se vacia despues."""
    from app.erp import normalizar_nombre, ultimas_compras_por_cliente
    from app.negocio.filtros import codigos_filtro

    codigos = codigos_filtro()
    filas = ultimas_compras_por_cliente(codigos)
    vida_util = negocio.listar_vida_util()
    maquinas = negocio.listar_maquinas()
    limite = (date.today() + timedelta(days=7)).isoformat()

    candidatas = {}
    for f in filas:
        clave = normalizar_nombre(f["cliente"])
        if not clave or f["codigo"] in vida_util or (clave, f["codigo"]) in maquinas or f["unidades"] <= 0:
            continue
        previa = candidatas.get((clave, f["codigo"]))
        if previa is None or f["fecha"] > previa["fecha"]:
            candidatas[(clave, f["codigo"])] = {**f, "clave_cliente": clave}

    productos, clientes, hechas = set(), set(), 0
    # Compras mas antiguas primero: dan una vida util realista (unos meses)
    for f in sorted(candidatas.values(), key=lambda x: x["fecha"]):
        if hechas >= faltan:
            break
        if f["codigo"] in productos or f["clave_cliente"] in clientes:
            continue
        dias = (date.today() - datetime.fromisoformat(f["fecha"]).date()).days
        meses = max(0.5, round((dias - 2) / negocio.DIAS_POR_MES / f["unidades"] * 2) / 2)
        proximo = negocio.calcular_proximo_contacto(f["fecha"], f["unidades"], meses, 1)
        if not proximo or proximo > limite:
            continue
        negocio.set_vida_util(f["codigo"], meses)
        negocio.set_maquinas(f["clave_cliente"], f["codigo"], 1)
        productos.add(f["codigo"])
        clientes.add(f["clave_cliente"])
        hechas += 1
        print(f"  + dado de alta: {f['cliente']} | {f['codigo']} | vida util {meses} meses, 1 maquina")
    return hechas


def enviar(reales=False, cantidad=3, completar=False):
    cfg = avisos.cargar_config()
    chats = avisos.destinatarios(cfg)
    alertas = _reales(cantidad) if reales else _ficticios()
    if reales and completar and len(alertas) < cantidad:
        if _completar(cantidad - len(alertas)):
            alertas = _reales(cantidad)
    if reales and not alertas:
        print("No hay alertas reales pendientes para usar en la prueba.")
        return
    nota = NOTA_REAL if reales else NOTA_FICTICIO
    for a in alertas:
        texto = avisos._texto(a) + "\n   " + nota
        for chat_id in chats:
            alerta_id = negocio.registrar_alerta_telegram(
                a["clave_cliente"], a["codigo"], chat_id, 0, texto, prueba=True
            )
            resultado = avisos.enviar_mensaje(cfg["token"], chat_id, texto, avisos._teclado(alerta_id))
            negocio.actualizar_message_id(alerta_id, resultado["message_id"])
        print(f"  - {a['cliente']} | {a['codigo']}")
    print(f"Mandados {len(alertas)} avisos de prueba ({'reales' if reales else 'ficticios'}) a {len(chats)} chat(s).")


def limpiar():
    conn = negocio.conectar()
    try:
        # Seguimientos registrados desde Telegram a traves de un aviso de prueba
        # (desde que se mando ese aviso): se deshacen para dejar al cliente como estaba.
        deshechos = 0
        avisos_prueba = conn.execute(
            "SELECT clave_cliente, codigo, MIN(creado_en) FROM alertas_telegram WHERE prueba = 1 "
            "GROUP BY clave_cliente, codigo"
        ).fetchall()
        for clave, codigo, desde in avisos_prueba:
            deshechos += conn.execute(
                "DELETE FROM seguimientos WHERE clave_cliente = ? AND codigo = ? AND fecha >= ? "
                "AND usuario LIKE '%(Telegram)'",
                (clave, codigo, desde),
            ).rowcount
        n_avisos = conn.execute("DELETE FROM alertas_telegram WHERE prueba = 1").rowcount
        # Restos de versiones anteriores del script (sin la marca de prueba)
        deshechos += conn.execute("DELETE FROM seguimientos WHERE clave_cliente LIKE ?", (PREFIJO + "%",)).rowcount
        n_avisos += conn.execute("DELETE FROM alertas_telegram WHERE clave_cliente LIKE ?", (PREFIJO + "%",)).rowcount
        conn.execute("DELETE FROM telegram_espera WHERE alerta_id NOT IN (SELECT id FROM alertas_telegram)")
        conn.commit()
    finally:
        conn.close()
    print(f"Borrados {n_avisos} avisos de prueba y deshechos {deshechos} seguimientos registrados en ellos.")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limpiar", action="store_true")
    p.add_argument("--reales", action="store_true")
    p.add_argument(
        "--completar",
        action="store_true",
        help="con --reales: si faltan alertas, da de alta vida util/maquinas de prueba en otros clientes",
    )
    p.add_argument("--cantidad", type=int, default=3, help="cuantos avisos reales mandar (con --reales)")
    args = p.parse_args()
    if args.limpiar:
        limpiar()
    else:
        enviar(reales=args.reales, cantidad=args.cantidad, completar=args.completar)
