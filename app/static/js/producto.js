// Pestana Buscar producto.
// ---- buscar producto (autocomplete local) ----
let catalogo = [];
fetchAuth('/api/productos').then(r => r.json()).then(d => { catalogo = d; });

const inputProducto = document.getElementById('inputProducto');
const sugProducto = document.getElementById('sugProducto');

inputProducto.addEventListener('input', () => {
  const q = inputProducto.value.trim().toLowerCase();
  if (q.length < 1) { sugProducto.classList.remove('activo'); return; }
  const matches = catalogo.filter(p =>
    p.codigo.toLowerCase().includes(q) || (p.nombre || '').toLowerCase().includes(q)
  ).slice(0, 15);
  if (matches.length === 0) { sugProducto.classList.remove('activo'); return; }
  sugProducto.innerHTML = matches.map(p =>
    `<div class="sugerencia" data-codigo="${p.codigo}"><span class="codigo">${p.codigo}</span><span>${p.nombre || ''}</span></div>`
  ).join('');
  sugProducto.classList.add('activo');
});

sugProducto.addEventListener('click', (e) => {
  const el = e.target.closest('.sugerencia');
  if (!el) return;
  inputProducto.value = el.dataset.codigo;
  sugProducto.classList.remove('activo');
  cargarProducto(el.dataset.codigo);
});

document.addEventListener('click', (e) => {
  if (!e.target.closest('.buscador')) {
    sugProducto.classList.remove('activo');
    sugCliente.classList.remove('activo');
    sugAgregar.classList.remove('activo');
  }
});

async function cargarProducto(codigo) {
  ultimoProducto = codigo;
  const cont = document.getElementById('resultadoProducto');
  cont.innerHTML = '<div class="cargando">Cargando línea de tiempo...</div>';
  try {
    const r = await fetchAuth('/api/producto/' + encodeURIComponent(codigo));
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    if (d.clientes.length === 0) {
      datosProductoActual = null;
      mapaProducto = new Map();
      cont.innerHTML = '<div class="vacio">Sin ventas registradas de este filtro desde 2024.</div>';
      return;
    }
    cont.innerHTML = `
      <div class="resultado-header">
        <h2>${d.codigo}</h2>
        <div class="sub">${fmt.format(Math.round(d.unidades_total))} unidades vendidas en total · ${d.clientes.length} clientes</div>
        <a class="btn-descargar" href="/api/exportar/producto/${encodeURIComponent(d.codigo)}.xlsx">⬇ Descargar Excel</a>
      </div>
      <div class="tarjetas">
        ${d.clientes.map(c => `
          <div class="tarjeta ${claseUrgencia(c.estado, c.compras[0].proximo_contacto)}">
            <div class="tarjeta-header">
              <span><span class="chevron">▸</span><span class="nombre nombre-click" data-legacy="${c.legacy_id ?? ''}" data-actual="${c.actual_id ?? ''}" data-nombre="${(c.cliente || '').replace(/"/g, '&quot;')}">${c.cliente || '(sin nombre)'}</span></span>
              <span class="total">${fmt.format(Math.round(c.unidades_total))} unidades</span>
            </div>
            <div class="tarjeta-detalle oculto">
              <div class="config-fila">
                <label>Vida útil: <input type="number" min="0.1" step="0.1" class="input-chico input-vida-util" data-codigo="${d.codigo}" value="${d.vida_util_meses ?? ''}" placeholder="meses"> meses</label>
                ${c.clave_cliente ? `<label>Máquinas del cliente: <input type="number" min="1" step="1" class="input-chico input-maquinas" data-clave="${c.clave_cliente}" data-codigo="${d.codigo}" value="${c.maquinas ?? ''}"></label>` : ''}
              </div>
              <div class="tarjeta-meta">
                <span class="ultima-compra">Última compra: ${fmtFecha(c.compras[0].fecha)}</span>
                ${badgeEstado(c.estado, c.compras[0].proximo_contacto, c.nota_estado)}
              </div>
              ${miniGrafica(c.compras)}
              ${bloqueSeguimiento(c.clave_cliente, d.codigo)}
              ${bloqueTimeline(c.compras, d.codigo)}
            </div>
          </div>
        `).join('')}
      </div>
    `;
    datosProductoActual = d;
    mapaProducto = new Map();
    const els = cont.querySelectorAll('.tarjeta');
    d.clientes.forEach((c, i) => {
      const clave = c.clave_cliente || `${c.legacy_id}|${c.actual_id}`;
      mapaProducto.set(clave, { el: els[i], data: c });
    });
  } catch (e) {
    cont.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
}
