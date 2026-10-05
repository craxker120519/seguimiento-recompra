// Cambio de pestana (barra fija arriba).
// ---- tabs ----
function activarTab(nombreTab) {
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('activo', t.dataset.tab === nombreTab));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('activo', p.id === 'panel-' + nombreTab));
  if (nombreTab === 'catalogo' && !catalogoActivo) cargarCatalogo();
  if (nombreTab === 'alertas') cargarAlertas();
  if (nombreTab === 'resultados') cargarResultados();
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => activarTab(tab.dataset.tab));
});
