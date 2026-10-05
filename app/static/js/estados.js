// Etiquetas de resultado, etiqueta y color de urgencia de cada estado y calculo local del proximo contacto.
const ETIQUETAS_RESULTADO = {
  contactado_esperar: 'Pidió esperar',
  vendio_de_nuevo: 'Volvió a comprar',
  cambio_proveedor: 'Cambió de proveedor',
  no_contesto: 'No contestó',
  no_aplica: 'No aplica',
};

// Combina el cálculo por fecha (vencido / próximo a vencer / normal) con el
// último seguimiento registrado (pendiente / resuelto / inactivo), que el
// backend ya resolvió en negocio.resolver_estado.
function badgeEstado(estado, proximoContacto, nota) {
  if (estado === 'pendiente') {
    return `<span class="proximo-contacto pendiente">Pendiente hasta ${fmtFecha(proximoContacto)}</span>`;
  }
  if (estado === 'resuelto') {
    return `<span class="proximo-contacto resuelto">Resuelto: volvió a comprar</span>`;
  }
  if (estado === 'descartado') {
    return `<span class="proximo-contacto inactivo">No aplica${nota ? ': ' + esc(nota) : ''}</span>`;
  }
  if (estado === 'esperando_factura') {
    // "nota" trae la fecha en que registraron "volvió a comprar"; proximoContacto = dia 15, cuando pasa a vencido
    return `<span class="proximo-contacto pendiente">⏳ Volvió a comprar el ${fmtFecha(nota)} · esperando factura · si no llega, se marca vencido el ${fmtFecha(proximoContacto)}</span>`;
  }
  if (estado === 'factura_vencida') {
    return `<span class="proximo-contacto vencido">Sin factura desde el ${fmtFecha(nota)} · contactar ya</span>`;
  }
  if (estado === 'inactivo') {
    return `<span class="proximo-contacto inactivo">Cambió de proveedor${nota ? ': ' + esc(nota) : ''}</span>`;
  }
  if (estado === 'reintentar') {
    // "nota" trae la fecha (YYYY-MM-DD) del intento en que no contestaron
    const base = 'No contestó' + (nota ? ' el ' + fmtFecha(nota) : '');
    if (estaVencido(proximoContacto)) return `<span class="proximo-contacto vencido">Reintentar ya (${base}; tocaba ${fmtFecha(proximoContacto)})</span>`;
    return `<span class="proximo-contacto alerta">${base} · reintentar ${fmtFecha(proximoContacto)}</span>`;
  }
  if (!proximoContacto) return `<span class="proximo-contacto sindatos">Próximo contacto: captura vida útil y máquinas</span>`;
  if (estaVencido(proximoContacto)) return `<span class="proximo-contacto vencido">Contactar ya (venció ${fmtFecha(proximoContacto)})</span>`;
  if (dentroDeUnaSemana(proximoContacto)) return `<span class="proximo-contacto alerta">Contactar pronto (vence ${fmtFecha(proximoContacto)})</span>`;
  return `<span class="proximo-contacto">Próximo contacto: ${fmtFecha(proximoContacto)}</span>`;
}

// Espejo en JS de negocio.calcular_proximo_contacto (Python), para poder
// recalcular al instante sin volver a pedirle nada al servidor. Solo se usa
// cuando estado === 'normal' (sin seguimiento activo que lo sustituya).
function calcularProximoContactoJS(fechaIso, unidades, meses, maquinas) {
  if (!meses || !maquinas) return null;
  const filtrosPorMaquina = unidades / maquinas;
  const mesesCobertura = filtrosPorMaquina * meses;
  const fecha = new Date(fechaIso);
  fecha.setDate(fecha.getDate() + Math.round(mesesCobertura * 30.44));
  return fecha.toISOString().slice(0, 10);
}

// Clase de color del borde izquierdo de la tarjeta, mismo criterio que el
// badge de texto, para poder distinguir urgencia de un vistazo en listas largas.
function claseUrgencia(estado, proximoContacto) {
  if (estado === 'pendiente') return 'urgencia-pendiente';
  if (estado === 'resuelto') return 'urgencia-resuelto';
  if (estado === 'esperando_factura') return 'urgencia-pendiente';
  if (estado === 'factura_vencida') return 'urgencia-vencido';
  if (estado === 'inactivo' || estado === 'descartado') return 'urgencia-inactivo';
  if (estado === 'reintentar') return estaVencido(proximoContacto) ? 'urgencia-vencido' : 'urgencia-alerta';
  if (!proximoContacto) return '';
  if (estaVencido(proximoContacto)) return 'urgencia-vencido';
  if (dentroDeUnaSemana(proximoContacto)) return 'urgencia-alerta';
  return '';
}

function actualizarMetaTarjeta(tarjetaEl, fechaUltima, proximoContacto, estado, nota) {
  if (!tarjetaEl) return;
  const metaEl = tarjetaEl.querySelector('.tarjeta-meta');
  if (!metaEl) return;
  metaEl.innerHTML = `<span class="ultima-compra">Última compra: ${fmtFecha(fechaUltima)}</span>${badgeEstado(estado, proximoContacto, nota)}`;
  tarjetaEl.className = 'tarjeta ' + claseUrgencia(estado, proximoContacto);
}

// Mini-grafica de barras (unidades por mes, ultimos 6 meses con compras) para
// ver de un vistazo si un cliente/producto esta comprando mas o menos.
