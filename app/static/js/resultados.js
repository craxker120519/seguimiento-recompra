// Pestana Resultados: casos por resultado, filtros, busqueda y abrir un caso.
// ---- pestaña "Resultados": clientes por resultado de su seguimiento ----
let diasResultados = 90;
let datosResultados = null;
let filtroResultado = 'todos';
let busquedaResultado = '';

async function cargarResultados() {
  const cont = document.getElementById('resultadosContenido');
  const sufijo = diasResultados ? '?dias=' + diasResultados : '';
  document.getElementById('resDescargar').href = '/api/exportar/resultados.xlsx' + sufijo;
  try {
    const r = await fetchAuth('/api/resultados' + sufijo);
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    datosResultados = d;
    renderResultados();
  } catch (e) {
    cont.innerHTML = '<div class="vacio">No se pudieron cargar los resultados.</div>';
  }
}

function renderResultados() {
  const d = datosResultados;
  const cont = document.getElementById('resultadosContenido');
  if (!d.total) {
    cont.innerHTML = '<div class="vacio">Aún no hay seguimientos registrados en este periodo. Cuando se empiecen a registrar (en la página o desde Telegram), aquí verás qué clientes volvieron a comprar, cuáles pidieron esperar, cuáles no contestaron y cuáles cambiaron de proveedor.</div>';
    return;
  }
  const t = d.totales;
  const tasa = d.tasa_recuperacion === null ? '—' : d.tasa_recuperacion + '%';
  const tile = (filtro, num, lbl, tono) => `
    <button type="button" class="res-kpi ${filtro === 'todos' ? 'todos' : (TONO_RESULTADO[filtro] || '')}${filtroResultado === filtro ? ' activo' : ''}" data-filtro="${filtro}" aria-pressed="${filtroResultado === filtro}">
      <div class="num">${num}</div><div class="lbl">${lbl}</div>
    </button>`;
  cont.innerHTML = `
    <div class="res-kpis">
      <div class="res-kpi fijo"><div class="num">${tasa}</div><div class="lbl">Recuperación<br><small>volvieron a comprar, de los casos resueltos</small></div></div>
      ${tile('todos', d.total, 'Casos atendidos<br><small>' + d.clientes + ' cliente' + (d.clientes !== 1 ? 's' : '') + '</small>')}
      ${tile('vendio_de_nuevo', t.vendio_de_nuevo, 'Volvieron a comprar')}
      ${tile('contactado_esperar', t.contactado_esperar, 'Pidieron esperar')}
      ${tile('no_contesto', t.no_contesto, 'No contestaron')}
      ${tile('cambio_proveedor', t.cambio_proveedor, 'Cambiaron de proveedor')}
      ${tile('no_aplica', t.no_aplica || 0, 'No aplican<br><small>descartados</small>')}
    </div>
    <div class="res-barra-herr">
      <span class="titulo" id="resTituloLista"></span>
      <input type="text" id="resBuscar" placeholder="Buscar cliente o producto..." autocomplete="off" value="${esc(busquedaResultado)}">
    </div>
    <div id="resLista"></div>`;
  pintarCasosResultados();
}

function detalleCaso(c) {
  if (c.resultado === 'contactado_esperar') {
    return `<div class="detalle">Recordar el <b>${fmtFecha(c.proximo_recordatorio)}</b></div>`;
  }
  if (c.resultado === 'no_contesto') {
    const intentos = c.intentos > 1 ? `<b>${c.intentos} intentos</b> sin respuesta` : 'Sin respuesta';
    return `<div class="detalle">${intentos}${c.nota ? ' · ' + esc(c.nota) : ''}</div>`;
  }
  if (c.resultado === 'no_aplica') {
    return c.nota ? `<div class="detalle"><b>Motivo:</b> ${esc(c.nota)}</div>` : '<div class="detalle sin">Sin motivo anotado</div>';
  }
  if (c.resultado === 'cambio_proveedor') {
    return c.nota ? `<div class="detalle"><b>Motivo:</b> ${esc(c.nota)}</div>` : '<div class="detalle sin">Sin motivo anotado</div>';
  }
  if (c.por_factura) {
    return `<div class="detalle">Factura nueva detectada en ERP <span style="color:var(--muted)">(antes: ${ETIQUETAS_RESULTADO[c.antes] || esc(c.antes)})</span></div>`;
  }
  if (c.sin_factura) {
    return c.factura_vencida
      ? '<div class="detalle"><b>Sin factura tras 15 días: hay que contactarlo</b></div>'
      : `<div class="detalle">⏳ Esperando su factura en ERP <span style="color:var(--muted)">· se recalcula solo al facturarse</span></div>`;
  }
  return c.nota ? `<div class="detalle">${esc(c.nota)}</div>` : '';
}

function pintarCasosResultados() {
  const q = busquedaResultado.trim().toLowerCase();
  const casos = datosResultados.casos.filter(c =>
    (filtroResultado === 'todos' || c.resultado === filtroResultado) &&
    (!q || (c.clave_cliente + ' ' + c.codigo + ' ' + (c.nombre_producto || '')).toLowerCase().includes(q)));
  document.getElementById('resTituloLista').textContent =
    (filtroResultado === 'todos' ? 'Todos los casos' : ETIQUETAS_RESULTADO[filtroResultado]) + ' · ' + casos.length;
  document.getElementById('resLista').innerHTML = casos.length ? casos.map(c => `
    <div class="res-caso ${TONO_RESULTADO[c.resultado] || ''}" role="link" tabindex="0" data-cliente="${esc(c.clave_cliente)}" data-codigo="${esc(c.codigo)}" title="Abrir su seguimiento">
      <div class="fila1"><span class="cliente">${esc(c.clave_cliente)}</span><span class="ir">Ver seguimiento ›</span><span class="etiqueta">${ETIQUETAS_RESULTADO[c.resultado] || esc(c.resultado)}</span></div>
      <div class="prod">${esc(c.codigo)}${c.nombre_producto ? ' — ' + esc(c.nombre_producto) : ''}</div>
      ${detalleCaso(c)}
      <div class="meta">${fmtFecha(c.fecha)}${c.por_factura ? ' · por factura' : ''}${c.seguimientos > 1 ? ' · ' + c.seguimientos + ' seguimientos' : ''}</div>
    </div>`).join('') : '<div class="vacio">No hay clientes con este resultado' + (q ? ' que coincidan con la búsqueda' : ' en el periodo') + '.</div>';
}

document.getElementById('resPeriodos').addEventListener('click', (e) => {
  const b = e.target.closest('.res-periodo');
  if (!b) return;
  diasResultados = b.dataset.dias ? parseInt(b.dataset.dias, 10) : null;
  document.querySelectorAll('#resPeriodos .res-periodo').forEach(x => x.classList.toggle('activo', x === b));
  cargarResultados();
});

document.getElementById('resultadosContenido').addEventListener('click', (e) => {
  const k = e.target.closest('.res-kpi[data-filtro]');
  if (!k) return;
  filtroResultado = filtroResultado === k.dataset.filtro && k.dataset.filtro !== 'todos' ? 'todos' : k.dataset.filtro;
  renderResultados();
});

// Tocar un caso lleva a ese cliente en "Buscar cliente", con el producto abierto y su seguimiento a la vista.
function abrirCasoResultados(caso) {
  activarTab('cliente');
  document.getElementById('inputCliente').value = caso.dataset.cliente;
  buscarClientePorNombre(caso.dataset.cliente, caso.dataset.codigo);
}

document.getElementById('resultadosContenido').addEventListener('click', (e) => {
  const caso = e.target.closest('.res-caso');
  if (caso) abrirCasoResultados(caso);
});

document.getElementById('resultadosContenido').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter' && e.key !== ' ') return;
  const caso = e.target.closest('.res-caso');
  if (!caso) return;
  e.preventDefault();
  abrirCasoResultados(caso);
});

document.getElementById('resultadosContenido').addEventListener('input', (e) => {
  if (e.target.id !== 'resBuscar') return;
  busquedaResultado = e.target.value;
  pintarCasosResultados();
});
