// Pestana Contactar hoy.
// ---- pestaña "Contactar hoy": todos los cliente+filtro vencidos o por
// vencer en los proximos 7 dias, ordenados por urgencia (igual que las
// alertas de Telegram, pero sin tener que revisar el chat) ----
// Las alertas de "volvió a comprar" sin factura llevan su propio estado; el resto se muestra por fecha.
const ESTADOS_FACTURA = ['esperando_factura', 'factura_vencida'];
const claseAlerta = (a) => ESTADOS_FACTURA.includes(a.estado) ? claseUrgencia(a.estado, a.proximo_contacto) : (a.vencido ? 'urgencia-vencido' : 'urgencia-alerta');
const badgeAlerta = (a) => badgeEstado(ESTADOS_FACTURA.includes(a.estado) ? a.estado : 'normal', a.proximo_contacto, a.nota_estado);

async function cargarAlertas() {
  const cont = document.getElementById('resultadoAlertas');
  cont.innerHTML = '<div class="cargando">Cargando...</div>';
  try {
    const r = await fetchAuth('/api/alertas');
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    if (d.length === 0) {
      cont.innerHTML = '<div class="vacio">No hay nadie por contactar hoy ni en los próximos 7 días.</div>';
      return;
    }
    cont.innerHTML = `
      <div class="resultado-header">
        <div class="sub">${d.length} cliente${d.length === 1 ? '' : 's'} por contactar, del más urgente al menos urgente</div>
      </div>
      <div class="tarjetas">
        ${d.map(a => `
          <div class="alerta-fila ${claseAlerta(a)}" data-nombre="${esc(a.cliente || '')}">
            <span>
              <span class="nombre">${esc(a.cliente) || '(sin nombre)'}</span><br>
              <span class="prod">${esc(a.codigo)} — ${esc(a.nombre_producto)}</span>
            </span>
            <span>${badgeAlerta(a)}</span>
          </div>
        `).join('')}
      </div>
    `;
  } catch (e) {
    cont.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
}

// ---- click en una fila de "Contactar hoy" lleva al cliente en la pestaña
// "Buscar cliente" (misma busqueda por nombre que ya existe) ----
document.addEventListener('click', (e) => {
  const fila = e.target.closest('.alerta-fila');
  if (!fila) return;
  activarTab('cliente');
  const nombre = fila.dataset.nombre;
  document.getElementById('inputCliente').value = nombre;
  buscarClientePorNombre(nombre);
});
