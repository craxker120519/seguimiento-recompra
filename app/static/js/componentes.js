// Piezas de una tarjeta: grafica por mes, formulario de seguimiento e historial de compras.
function miniGrafica(compras) {
  const porMes = {};
  compras.forEach(c => {
    const mes = c.fecha.slice(0, 7);
    porMes[mes] = (porMes[mes] || 0) + c.unidades;
  });
  const meses = Object.keys(porMes).sort().slice(-6);
  if (meses.length < 2) return '';
  const max = Math.max(...meses.map(m => porMes[m]));
  const barras = meses.map(m => {
    const alto = Math.max(3, Math.round((porMes[m] / max) * 40));
    const etiqueta = m.slice(5, 7) + '/' + m.slice(2, 4);
    return `<div class="barra-mes" title="${fmt.format(Math.round(porMes[m]))} unidades en ${m}"><div class="barra" style="height:${alto}px"></div><span>${etiqueta}</span></div>`;
  }).join('');
  return `<div class="mini-grafica">${barras}</div>`;
}

const ICONO_SEG = {
  contactado_esperar: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  vendio_de_nuevo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M8 12.5l2.7 2.7L16 9.5"/></svg>',
  cambio_proveedor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 7h11l-3-3M17 17H6l3 3"/></svg>',
  no_contesto: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4h4l2 5-2.5 1.5a11 11 0 005 5L15 13l5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z"/><path d="M16 3l5 5M21 3l-5 5"/></svg>',
};
ICONO_SEG.no_aplica = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M5.6 5.6l12.8 12.8"/></svg>';
const TONO_RESULTADO = {
  contactado_esperar: 'tono-esperar', vendio_de_nuevo: 'tono-compro',
  cambio_proveedor: 'tono-proveedor', no_contesto: 'tono-nocontesto', no_aplica: 'tono-noaplica',
};
const ATAJOS_FECHA = [['En 3 días', 3], ['En 1 semana', 7], ['En 2 semanas', 14], ['En 1 mes', 30]];
const ATAJOS_NOTA = ['Llamé, sin respuesta', 'Mandé WhatsApp, sin respuesta', 'Mandé correo, sin respuesta'];
let contadorFormSeg = 0;

function bloqueSeguimiento(clave, codigo) {
  if (!clave) return '';
  const grupo = 'seg-res-' + (++contadorFormSeg);
  const opciones = Object.keys(ETIQUETAS_RESULTADO).map((valor, i) => `
        <label class="seg-opcion ${TONO_RESULTADO[valor]}">
          <input type="radio" class="sel-resultado" name="${grupo}" value="${valor}"${i === 0 ? ' checked' : ''}>
          <span class="cuerpo">${ICONO_SEG[valor]}${ETIQUETAS_RESULTADO[valor]}</span>
        </label>`).join('');
  const atajosFecha = ATAJOS_FECHA.map(([texto, dias]) => `<button type="button" class="seg-atajo" data-dias="${dias}">${texto}</button>`).join('');
  const atajosNota = ATAJOS_NOTA.map(texto => `<button type="button" class="seg-atajo atajo-nota">${texto}</button>`).join('');
  return `
    <div class="seguimiento-bloque">
      <button type="button" class="btn-seguimiento-toggle" aria-expanded="false" data-clave="${clave}" data-codigo="${codigo}">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/></svg>
        Registrar seguimiento
      </button>
      <div class="form-seguimiento oculto" data-clave="${clave}" data-codigo="${codigo}">
        <div class="seg-titulo"><span>¿Qué pasó con este cliente?</span><button type="button" class="seg-cerrar" title="Cerrar" aria-label="Cerrar">×</button></div>
        <div class="seg-opciones">${opciones}
        </div>
        <div class="seg-campo campo-fecha">
          <label class="seg-label">Recordarme el día</label>
          <input type="date" class="input-fecha-recordatorio">
          <div class="seg-atajos">${atajosFecha}</div>
        </div>
        <div class="seg-campo campo-nota oculto">
          <label class="seg-label etiqueta-nota">Nota <small>(opcional)</small></label>
          <textarea class="input-nota" rows="3"></textarea>
          <div class="seg-atajos atajos-nota oculto">${atajosNota}</div>
          <label class="seg-check campo-todos oculto"><input type="checkbox" class="chk-todos"><span class="txt-todos"></span></label>
        </div>
        <div class="seg-error oculto"></div>
        <div class="seg-acciones">
          <button type="button" class="btn-cancelar-seguimiento">Cancelar</button>
          <button type="button" class="btn-guardar-seguimiento">Guardar seguimiento</button>
        </div>
        <div class="historial-seguimiento oculto" data-historial="${clave}|${codigo}"></div>
      </div>
    </div>
  `;
}

function bloqueTimeline(compras, filtroTexto) {
  const eventosHTML = compras.map(ev => `
    <div class="evento"><span class="fecha">${fmtFecha(ev.fecha)}</span><span class="detalle">${fmt.format(Math.round(ev.unidades))} filtros de ${filtroTexto} · precio: ${fmtMoney(ev.precio_unitario, ev.moneda)} c/u · total: ${fmtMoney(ev.monto, ev.moneda)}</span></div>
  `).join('');
  return `
    <button type="button" class="btn-toggle-timeline">▾ Ocultar historial (${compras.length} compras)</button>
    <div class="timeline">${eventosHTML}</div>
  `;
}
