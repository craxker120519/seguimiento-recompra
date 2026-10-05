// Estado en memoria de lo ultimo cargado y edicion de vida util y maquinas.
// ---- estado en memoria de lo último cargado, para actualizar tarjetas
// sin volver a pedir nada al servidor ni perder el scroll ----
let ultimoProducto = null;
let ultimoCliente = null;
let catalogoActivo = false;
let datosProductoActual = null;
let datosClienteActual = null;
let mapaProducto = new Map();
let mapaCliente = new Map();

function aplicarVidaUtilLocal(codigo, meses) {
  if (datosProductoActual && datosProductoActual.codigo === codigo) {
    datosProductoActual.vida_util_meses = meses;
    mapaProducto.forEach(({ el, data: c }) => {
      if (c.estado !== 'normal') return;
      const ultima = c.compras[0];
      ultima.proximo_contacto = calcularProximoContactoJS(ultima.fecha, ultima.unidades, meses, c.maquinas);
      actualizarMetaTarjeta(el, ultima.fecha, ultima.proximo_contacto, c.estado, c.nota_estado);
    });
  }
  if (datosClienteActual) {
    const entry = mapaCliente.get(codigo);
    if (entry && entry.data.estado === 'normal') {
      entry.data.vida_util_meses = meses;
      const ultima = entry.data.compras[0];
      ultima.proximo_contacto = calcularProximoContactoJS(ultima.fecha, ultima.unidades, meses, entry.data.maquinas);
      actualizarMetaTarjeta(entry.el, ultima.fecha, ultima.proximo_contacto, entry.data.estado, entry.data.nota_estado);
    }
  }
  const item = catalogoCompleto.find(f => f.codigo === codigo);
  if (item) item.vida_util_meses = meses;
}

function aplicarMaquinasLocal(clave, codigo, cantidad) {
  if (datosProductoActual && datosProductoActual.codigo === codigo) {
    const entry = mapaProducto.get(clave);
    if (entry && entry.data.estado === 'normal') {
      entry.data.maquinas = cantidad;
      const ultima = entry.data.compras[0];
      ultima.proximo_contacto = calcularProximoContactoJS(ultima.fecha, ultima.unidades, datosProductoActual.vida_util_meses, cantidad);
      actualizarMetaTarjeta(entry.el, ultima.fecha, ultima.proximo_contacto, entry.data.estado, entry.data.nota_estado);
    }
  }
  if (datosClienteActual && datosClienteActual.clave_cliente === clave) {
    const entry = mapaCliente.get(codigo);
    if (entry && entry.data.estado === 'normal') {
      entry.data.maquinas = cantidad;
      const ultima = entry.data.compras[0];
      ultima.proximo_contacto = calcularProximoContactoJS(ultima.fecha, ultima.unidades, entry.data.vida_util_meses, cantidad);
      actualizarMetaTarjeta(entry.el, ultima.fecha, ultima.proximo_contacto, entry.data.estado, entry.data.nota_estado);
    }
  }
}

document.addEventListener('change', async (e) => {
  const vi = e.target.closest('.input-vida-util');
  if (vi) {
    const meses = parseFloat(vi.value);
    if (isNaN(meses) || meses <= 0) return;
    const codigo = vi.dataset.codigo;
    await fetchAuth('/api/vida-util', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo, meses }),
    });
    aplicarVidaUtilLocal(codigo, meses);
    return;
  }
  const mq = e.target.closest('.input-maquinas');
  if (mq) {
    const cantidad = parseInt(mq.value, 10);
    if (isNaN(cantidad) || cantidad <= 0 || !mq.dataset.clave) return;
    const codigo = mq.dataset.codigo;
    const clave = mq.dataset.clave;
    await fetchAuth('/api/maquinas', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ clave_cliente: clave, codigo, cantidad }),
    });
    aplicarMaquinasLocal(clave, codigo, cantidad);
    return;
  }
  const fechaSeg = e.target.closest('.input-fecha-recordatorio');
  if (fechaSeg) {
    fechaSeg.closest('.form-seguimiento').querySelectorAll('.seg-atajo[data-dias]').forEach(b => b.classList.remove('activo'));
    return;
  }
  const sel = e.target.closest('.sel-resultado');
  if (sel) actualizarCamposSeguimiento(sel.closest('.form-seguimiento'));
});

// Muestra solo los campos que aplican al resultado elegido (fecha para "Pidió
// esperar", nota para "Cambió de proveedor" / "No contestó").
