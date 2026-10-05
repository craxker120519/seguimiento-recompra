// Clics entre vistas: cliente a producto, producto a cliente y abrir o cerrar una tarjeta.
// ---- click en el nombre de un cliente (desde la vista de producto) lleva
// a su historial completo de filtros en la pestaña "Buscar cliente" ----
document.addEventListener('click', (e) => {
  const el = e.target.closest('.nombre-click');
  if (!el) return;
  activarTab('cliente');
  document.getElementById('inputCliente').value = el.dataset.nombre;
  cargarCliente(el.dataset.legacy, el.dataset.actual);
});

// ---- click en el código de un producto (desde la vista de cliente) lleva
// a su historial completo de TODOS los clientes en "Buscar producto" ----
document.addEventListener('click', (e) => {
  const el = e.target.closest('.codigo-click');
  if (!el) return;
  activarTab('producto');
  document.getElementById('inputProducto').value = el.dataset.codigo;
  cargarProducto(el.dataset.codigo);
});

// ---- expandir/contraer una tarjeta completa: por default solo se ve el
// nombre/código y el total; al picarle se abre todo lo demás (vida útil,
// máquinas, próximo contacto, seguimiento, historial de compras) ----
document.addEventListener('click', (e) => {
  if (e.target.closest('.nombre-click') || e.target.closest('.codigo-click')) return;
  const header = e.target.closest('.tarjeta-header');
  if (!header) return;
  const tarjeta = header.closest('.tarjeta');
  const detalle = tarjeta.querySelector('.tarjeta-detalle');
  const chevron = header.querySelector('.chevron');
  const oculto = detalle.classList.toggle('oculto');
  if (chevron) chevron.textContent = oculto ? '▸' : '▾';
});
