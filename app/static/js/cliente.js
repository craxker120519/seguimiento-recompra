// Pestana Buscar cliente y abrir el producto de un caso.
// ---- buscar cliente (server-side, con debounce) ----
const inputCliente = document.getElementById('inputCliente');
const sugCliente = document.getElementById('sugCliente');
const estadoBusquedaCliente = document.getElementById('estadoBusquedaCliente');
let debounceTimer = null;

inputCliente.addEventListener('input', () => {
  clearTimeout(debounceTimer);
  const q = inputCliente.value.trim();
  estadoBusquedaCliente.textContent = '';
  if (q.length < 2) { sugCliente.classList.remove('activo'); return; }
  debounceTimer = setTimeout(async () => {
    try {
      const r = await fetchAuth('/api/clientes?q=' + encodeURIComponent(q));
      const d = await r.json();
      if (!Array.isArray(d) || d.length === 0) {
        sugCliente.classList.remove('activo');
        estadoBusquedaCliente.textContent = 'No se encontró ningún cliente con ese nombre.';
        return;
      }
      estadoBusquedaCliente.textContent = `${d.length} cliente${d.length === 1 ? '' : 's'} encontrado${d.length === 1 ? '' : 's'}.`;
      sugCliente.innerHTML = d.map(c =>
        `<div class="sugerencia" data-legacy="${c.legacy_id ?? ''}" data-actual="${c.actual_id ?? ''}"><span>${c.nombre}</span></div>`
      ).join('');
      sugCliente.classList.add('activo');
    } catch (e) {
      sugCliente.classList.remove('activo');
      estadoBusquedaCliente.textContent = e.message;
    }
  }, 300);
});

sugCliente.addEventListener('click', (e) => {
  const el = e.target.closest('.sugerencia');
  if (!el) return;
  inputCliente.value = el.querySelector('span').textContent;
  sugCliente.classList.remove('activo');
  estadoBusquedaCliente.textContent = '';
  cargarCliente(el.dataset.legacy, el.dataset.actual);
});

// ---- usado desde "Contactar hoy": busca por nombre exacto y abre el
// primer resultado directo, sin que el usuario tenga que volver a elegirlo ----
async function buscarClientePorNombre(nombre, codigoAbrir) {
  estadoBusquedaCliente.textContent = '';
  try {
    const r = await fetchAuth('/api/clientes?q=' + encodeURIComponent(nombre));
    const d = await r.json();
    if (!Array.isArray(d) || d.length === 0) {
      document.getElementById('resultadoCliente').innerHTML = '';
      estadoBusquedaCliente.textContent = 'No se encontró ningún cliente con ese nombre.';
      return;
    }
    // Si varios nombres se parecen, el que coincide exactamente; si no, el primero.
    const exacto = d.find(c => (c.nombre || '').trim().toUpperCase() === nombre.trim().toUpperCase()) || d[0];
    cargarCliente(exacto.legacy_id, exacto.actual_id, codigoAbrir);
  } catch (e) {
    estadoBusquedaCliente.textContent = e.message;
  }
}

// Expande la tarjeta del producto, abre "Registrar seguimiento" con su historial y la deja a la vista.
function abrirProductoDelCliente(codigo) {
  const entrada = mapaCliente.get(codigo);
  if (!entrada) return;
  const tarjeta = entrada.el;
  tarjeta.querySelector('.tarjeta-detalle').classList.remove('oculto');
  const chevron = tarjeta.querySelector('.tarjeta-header .chevron');
  if (chevron) chevron.textContent = '▾';
  const toggle = tarjeta.querySelector('.btn-seguimiento-toggle');
  if (toggle && toggle.getAttribute('aria-expanded') !== 'true') toggle.click();
  tarjeta.scrollIntoView({ behavior: 'smooth', block: 'start' });
  tarjeta.classList.add('resaltada');
}

async function cargarCliente(legacyId, actualId, codigoAbrir) {
  ultimoCliente = { legacyId, actualId };
  const cont = document.getElementById('resultadoCliente');
  cont.innerHTML = '<div class="cargando">Cargando línea de tiempo...</div>';
  try {
    const params = new URLSearchParams();
    if (legacyId) params.set('legacy_id', legacyId);
    if (actualId) params.set('actual_id', actualId);
    const r = await fetchAuth(`/api/cliente?${params.toString()}`);
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    if (d.productos.length === 0) {
      datosClienteActual = null;
      mapaCliente = new Map();
      cont.innerHTML = '<div class="vacio">Sin compras de filtros registradas desde 2024.</div>';
      return;
    }
    cont.innerHTML = `
      <div class="resultado-header">
        <h2>${d.cliente || '(sin nombre)'}</h2>
        <div class="sub">${d.productos.length} filtros distintos comprados</div>
        <a class="btn-descargar" href="/api/exportar/cliente.xlsx?${legacyId ? 'legacy_id=' + encodeURIComponent(legacyId) : ''}${actualId ? '&actual_id=' + encodeURIComponent(actualId) : ''}">⬇ Descargar Excel</a>
      </div>
      <div class="tarjetas">
        ${d.productos.map(p => `
          <div class="tarjeta ${claseUrgencia(p.estado, p.compras[0].proximo_contacto)}">
            <div class="tarjeta-header">
              <span class="nombre"><span class="chevron">▸</span><span class="etiqueta codigo-click" data-codigo="${p.codigo}" style="margin-right:6px;">${p.codigo}</span>${p.nombre || ''}</span>
              <span class="total">${fmt.format(Math.round(p.unidades_total))} unidades</span>
            </div>
            <div class="tarjeta-detalle oculto">
              <div class="config-fila">
                <label>Vida útil: <input type="number" min="0.1" step="0.1" class="input-chico input-vida-util" data-codigo="${p.codigo}" value="${p.vida_util_meses ?? ''}" placeholder="meses"> meses</label>
                ${d.clave_cliente ? `<label>Máquinas del cliente: <input type="number" min="1" step="1" class="input-chico input-maquinas" data-clave="${d.clave_cliente}" data-codigo="${p.codigo}" value="${p.maquinas ?? ''}"></label>` : ''}
              </div>
              <div class="tarjeta-meta">
                <span class="ultima-compra">Última compra: ${fmtFecha(p.compras[0].fecha)}</span>
                ${badgeEstado(p.estado, p.compras[0].proximo_contacto, p.nota_estado)}
              </div>
              ${miniGrafica(p.compras)}
              ${bloqueSeguimiento(d.clave_cliente, p.codigo)}
              ${bloqueTimeline(p.compras, p.codigo)}
            </div>
          </div>
        `).join('')}
      </div>
    `;
    datosClienteActual = d;
    mapaCliente = new Map();
    const els = cont.querySelectorAll('.tarjeta');
    d.productos.forEach((p, i) => {
      mapaCliente.set(p.codigo, { el: els[i], data: p });
    });
    if (codigoAbrir) abrirProductoDelCliente(codigoAbrir);
  } catch (e) {
    cont.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
}
