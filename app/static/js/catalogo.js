// Pestana Catalogo y alta de filtros nuevos.
// ---- pestaña Catálogo: lista completa + captura de vida útil sin buscar ----
let catalogoCompleto = [];

function renderCatalogo(lista) {
  const cont = document.getElementById('listaCatalogo');
  if (lista.length === 0) {
    cont.innerHTML = '<div class="vacio">Sin resultados.</div>';
    return;
  }
  cont.innerHTML = `
    <div class="catalogo-lista">
      ${lista.map(f => `
        <div class="catalogo-fila">
          <span class="catalogo-codigo codigo-click" data-codigo="${f.codigo}">${f.codigo}</span>
          <span class="catalogo-nombre">${f.nombre || ''}</span>
          <label class="catalogo-vu">Vida útil: <input type="number" min="0.1" step="0.1" class="input-chico input-vida-util" data-codigo="${f.codigo}" value="${f.vida_util_meses ?? ''}" placeholder="meses"> meses</label>
        </div>
      `).join('')}
    </div>
  `;
}

async function cargarCatalogo() {
  catalogoActivo = true;
  const cont = document.getElementById('listaCatalogo');
  cont.innerHTML = '<div class="cargando">Cargando catálogo...</div>';
  try {
    const r = await fetchAuth('/api/catalogo');
    const d = await r.json();
    if (d.error) throw new Error(d.error);
    catalogoCompleto = d;
    renderCatalogo(catalogoCompleto);
  } catch (e) {
    cont.innerHTML = `<div class="error">Error: ${e.message}</div>`;
  }
}

document.getElementById('filtroCatalogo').addEventListener('input', (e) => {
  const q = e.target.value.trim().toLowerCase();
  const filtrados = q.length === 0 ? catalogoCompleto : catalogoCompleto.filter(f =>
    f.codigo.toLowerCase().includes(q) || (f.nombre || '').toLowerCase().includes(q)
  );
  renderCatalogo(filtrados);
});

// ---- agregar filtro nuevo, buscando en el catálogo completo de ERP ----
const inputAgregar = document.getElementById('inputAgregar');
const sugAgregar = document.getElementById('sugAgregar');
let debounceAgregar = null;

inputAgregar.addEventListener('input', () => {
  clearTimeout(debounceAgregar);
  const q = inputAgregar.value.trim();
  if (q.length < 2) { sugAgregar.classList.remove('activo'); return; }
  debounceAgregar = setTimeout(async () => {
    try {
      const r = await fetchAuth('/api/catalogo/buscar?q=' + encodeURIComponent(q));
      const d = await r.json();
      if (!Array.isArray(d) || d.length === 0) { sugAgregar.classList.remove('activo'); return; }
      sugAgregar.innerHTML = d.map(p => `
        <div class="agregar-fila">
          <span><span class="codigo" style="color:var(--accent); font-weight:600; margin-right:8px;">${p.codigo}</span>${p.nombre || ''}</span>
          <button type="button" class="btn-agregar" data-codigo="${p.codigo}">Agregar</button>
        </div>
      `).join('');
      sugAgregar.classList.add('activo');
    } catch (e) { /* silencioso */ }
  }, 300);
});

sugAgregar.addEventListener('click', async (e) => {
  const btn = e.target.closest('.btn-agregar');
  if (!btn) return;
  btn.disabled = true;
  btn.textContent = 'Agregando...';
  try {
    await fetchAuth('/api/catalogo/agregar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ codigo: btn.dataset.codigo }),
    });
    inputAgregar.value = '';
    sugAgregar.classList.remove('activo');
    fetchAuth('/api/productos').then(r => r.json()).then(d => { catalogo = d; });
    cargarCatalogo();
  } catch (e) { /* silencioso */ }
});
