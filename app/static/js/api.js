// Peticiones al servidor: redirige al login si la sesion expiro.
// ---- sesión: redirige a /login si el servidor dice que no hay sesión,
// en vez de que el fetch truene tratando de leer HTML como JSON ----
async function fetchAuth(url, opts) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 20000);
  let r;
  try {
    r = await fetch(url, { ...(opts || {}), signal: controller.signal });
  } catch (e) {
    throw new Error('No se pudo conectar con el servidor. Revisa tu conexión e intenta de nuevo.');
  } finally {
    clearTimeout(timeoutId);
  }
  if (r.status === 401) {
    window.location.href = '/login';
    throw new Error('no autenticado');
  }
  return r;
}

fetchAuth('/api/sesion').then(r => r.json()).then(d => {
  if (d.nombre) document.getElementById('nombreUsuario').textContent = d.nombre;
  if (d.rol === 'admin') document.getElementById('linkUsuarios').style.display = 'inline';
}).catch(() => {});

fetchAuth('/api/version').then(r => r.json()).then(d => {
  if (d.version) document.getElementById('footerVersion').textContent = ' · v' + d.version;
}).catch(() => {});
