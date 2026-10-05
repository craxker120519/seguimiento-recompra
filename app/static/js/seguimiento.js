// Formulario de seguimiento: campos segun el resultado, guardar, historial y sus clics.
function actualizarCamposSeguimiento(form) {
  const valor = form.querySelector('.sel-resultado:checked').value;
  form.querySelector('.campo-fecha').classList.toggle('oculto', valor !== 'contactado_esperar');
  const conNota = valor === 'cambio_proveedor' || valor === 'no_contesto' || valor === 'no_aplica';
  form.querySelector('.campo-nota').classList.toggle('oculto', !conNota);
  form.querySelector('.atajos-nota').classList.toggle('oculto', valor !== 'no_contesto');
  form.querySelector('.etiqueta-nota').innerHTML = {
    no_contesto: '¿Qué hiciste para comunicarte? <small>(opcional)</small>',
    no_aplica: 'Motivo por el que no aplica <small>(obligatorio: se deja de avisar de este caso)</small>',
  }[valor] || 'Motivo del cambio de proveedor <small>(opcional)</small>';
  form.querySelector('.input-nota').placeholder = {
    no_contesto: 'Ej. Llamé dos veces y mandé WhatsApp; nadie contestó',
    no_aplica: 'Ej. Cerró la empresa · Ya no usa este filtro · La venta no se va a facturar',
  }[valor] || 'Ej. Le dieron mejor precio';
  // "No aplica" puede aplicarse a todos los productos de este cliente (solo si su ficha esta abierta)
  const todos = form.querySelector('.campo-todos');
  const productos = datosClienteActual && datosClienteActual.clave_cliente === form.dataset.clave ? datosClienteActual.productos.length : 0;
  todos.classList.toggle('oculto', !(valor === 'no_aplica' && productos > 1));
  if (productos > 1) form.querySelector('.txt-todos').textContent = `Aplicar a los ${productos} productos de este cliente (por ejemplo, si cerró)`;
  if (valor !== 'no_aplica') form.querySelector('.chk-todos').checked = false;
  form.querySelector('.seg-error').classList.add('oculto');
}

function cerrarFormSeguimiento(form) {
  form.classList.add('oculto');
  form.closest('.seguimiento-bloque').querySelector('.btn-seguimiento-toggle').setAttribute('aria-expanded', 'false');
}

async function guardarSeguimiento(btn) {
  const form = btn.closest('.form-seguimiento');
  const clave = form.dataset.clave;
  const codigo = form.dataset.codigo;
  const resultado = form.querySelector('.sel-resultado:checked').value;
  const proximo_recordatorio = resultado === 'contactado_esperar' ? (form.querySelector('.input-fecha-recordatorio').value || null) : null;
  const conNota = resultado === 'cambio_proveedor' || resultado === 'no_contesto' || resultado === 'no_aplica';
  const nota = conNota ? (form.querySelector('.input-nota').value.trim() || null) : null;
  const error = form.querySelector('.seg-error');
  if (resultado === 'contactado_esperar' && !proximo_recordatorio) {
    error.textContent = 'Elige el día en que quieres que se te vuelva a recordar.';
    error.classList.remove('oculto');
    return;
  }
  if (resultado === 'no_aplica' && (!nota || nota.length < 3)) {
    error.textContent = 'Escribe el motivo por el que no aplica.';
    error.classList.remove('oculto');
    return;
  }
  const codigos = resultado === 'no_aplica' && form.querySelector('.chk-todos').checked && datosClienteActual
    ? datosClienteActual.productos.map(p => p.codigo) : undefined;
  error.classList.add('oculto');
  btn.disabled = true;
  btn.textContent = 'Guardando...';
  try {
    await fetchAuth('/api/seguimiento', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clave_cliente: clave, codigo, resultado, proximo_recordatorio, nota, codigos }),
    });
    if (ultimoProducto) cargarProducto(ultimoProducto);
    if (ultimoCliente) cargarCliente(ultimoCliente.legacyId, ultimoCliente.actualId, codigo);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Guardar seguimiento';
  }
}

async function mostrarHistorialSeguimiento(cont, clave, codigo) {
  cont.textContent = 'Cargando...';
  try {
    const r = await fetchAuth(`/api/seguimiento?clave_cliente=${encodeURIComponent(clave)}&codigo=${encodeURIComponent(codigo)}`);
    const historial = await r.json();
    if (!Array.isArray(historial) || historial.length === 0) {
      cont.innerHTML = '<div class="hs-titulo">Historial</div><div class="vacio">Aún no hay seguimientos registrados.</div>';
      return;
    }
    cont.innerHTML = '<div class="hs-titulo">Historial</div><div class="hs-lista">' + historial.map(h => `
      <div class="hs-item ${TONO_RESULTADO[h.resultado] || ''}">
        <div class="hs-cab"><span class="hs-res">${esc(ETIQUETAS_RESULTADO[h.resultado] || h.resultado)}</span><span class="hs-fecha">${fmtFecha(h.fecha)}</span></div>
        ${h.nota ? `<div class="hs-nota">${esc(h.nota)}</div>` : ''}
        ${h.usuario ? `<div class="hs-quien">${esc(h.usuario)}</div>` : ''}
      </div>
    `).join('') + '</div>';
  } catch (e) {
    cont.textContent = 'Error al cargar el historial.';
  }
}

document.addEventListener('click', (e) => {
  const toggleSeg = e.target.closest('.btn-seguimiento-toggle');
  if (toggleSeg) {
    const bloque = toggleSeg.closest('.seguimiento-bloque');
    const form = bloque.querySelector('.form-seguimiento');
    const historial = bloque.querySelector('.historial-seguimiento');
    const abrir = form.classList.contains('oculto');
    form.classList.toggle('oculto', !abrir);
    toggleSeg.setAttribute('aria-expanded', String(abrir));
    if (abrir) {
      actualizarCamposSeguimiento(form);
      historial.classList.remove('oculto');
      mostrarHistorialSeguimiento(historial, toggleSeg.dataset.clave, toggleSeg.dataset.codigo);
    }
    return;
  }
  if (e.target.closest('.seg-cerrar') || e.target.closest('.btn-cancelar-seguimiento')) {
    cerrarFormSeguimiento(e.target.closest('.form-seguimiento'));
    return;
  }
  const atajoFecha = e.target.closest('.seg-atajo[data-dias]');
  if (atajoFecha) {
    const form = atajoFecha.closest('.form-seguimiento');
    const f = new Date();
    f.setDate(f.getDate() + parseInt(atajoFecha.dataset.dias, 10));
    const iso = f.getFullYear() + '-' + String(f.getMonth() + 1).padStart(2, '0') + '-' + String(f.getDate()).padStart(2, '0');
    form.querySelector('.input-fecha-recordatorio').value = iso;
    form.querySelectorAll('.seg-atajo[data-dias]').forEach(b => b.classList.toggle('activo', b === atajoFecha));
    form.querySelector('.seg-error').classList.add('oculto');
    return;
  }
  const atajoNota = e.target.closest('.atajo-nota');
  if (atajoNota) {
    const area = atajoNota.closest('.form-seguimiento').querySelector('.input-nota');
    area.value = area.value.trim() ? area.value.trim() + ' · ' + atajoNota.textContent : atajoNota.textContent;
    area.focus();
    return;
  }
  const guardarBtn = e.target.closest('.btn-guardar-seguimiento');
  if (guardarBtn) {
    guardarSeguimiento(guardarBtn);
    return;
  }
  const timelineBtn = e.target.closest('.btn-toggle-timeline');
  if (timelineBtn) {
    const tl = timelineBtn.nextElementSibling;
    const oculto = tl.classList.toggle('oculto');
    const n = tl.querySelectorAll('.evento').length;
    timelineBtn.textContent = (oculto ? '▸ Ver historial (' : '▾ Ocultar historial (') + n + ' compras)';
    return;
  }
});
