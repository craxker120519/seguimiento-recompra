// Pagina de usuarios: alta, contrasenas, destinatarios de Telegram e historial de cambios.
// Mismas reglas que auth.validar_password en el servidor (que es quien de verdad las exige).
function motivoPasswordInvalida(p) {
  if (!p || p.length < 10) return 'Debe tener al menos 10 caracteres.';
  if (/^\d+$/.test(p)) return 'No puede ser solo números.';
  if (new Set(p).size < 4) return 'Es demasiado repetitiva.';
  return null;
}

let _esAdmin = false;
let _usuarios = [];

async function cargarUsuarios() {
  const r = await fetch('/api/usuarios');
  _usuarios = await r.json();
  renderTablaUsuarios();
}

function renderTablaUsuarios() {
  document.querySelector('#tablaUsuarios tbody').innerHTML = _usuarios.map(u => `
    <tr data-fila-usuario="${u.id}">
      <td>${u.nombre}</td>
      <td>${u.username}</td>
      <td><span class="badge-rol ${u.rol}">${u.rol}</span></td>
      <td>${(u.creado_en || '').slice(0,10)}</td>
      <td class="acciones">${_esAdmin ? `<button type="button" class="btn-link btn-cambiar-password" data-id="${u.id}" data-nombre="${u.nombre}">Cambiar contraseña</button>` : ''}</td>
    </tr>
  `).join('');
}

function abrirFormPassword(fila, usuarioId, nombre) {
  cerrarFormsPassword();
  const tr = document.createElement('tr');
  tr.className = 'fila-password';
  tr.innerHTML = `
    <td colspan="5">
      <div class="form-password-inline">
        <div>
          <label>Nueva contraseña para ${nombre}</label>
          <input type="password" class="input-password-nueva" autocomplete="new-password" placeholder="Mínimo 10 caracteres">
        </div>
        <div>
          <label>Confirmar</label>
          <input type="password" class="input-password-confirmar">
        </div>
        <button type="button" class="chico btn-guardar-password" data-id="${usuarioId}">Guardar</button>
        <button type="button" class="chico secundario btn-cancelar-password">Cancelar</button>
      </div>
      <div class="mensaje mensaje-password-inline"></div>
    </td>
  `;
  fila.after(tr);
}

function cerrarFormsPassword() {
  document.querySelectorAll('.fila-password').forEach(f => f.remove());
}

async function verificarRol() {
  const r = await fetch('/api/sesion');
  const d = await r.json();
  _esAdmin = d.rol === 'admin';
  if (!_esAdmin) {
    document.getElementById('filaAccionesUsuarios').style.display = 'none';
    document.getElementById('avisoSoloAdmin').style.display = 'block';
    document.getElementById('cajaInvitar').style.display = 'none';
    document.getElementById('cajaInvitarSoloLectura').style.display = 'block';
  }
  renderTablaUsuarios();
}

let _chatsTelegram = [];

async function cargarChatsTelegram() {
  const r = await fetch('/api/telegram/chats');
  _chatsTelegram = await r.json();
  document.querySelector('#tablaTelegram tbody').innerHTML = _chatsTelegram.length === 0
    ? '<tr><td colspan="4" style="color:var(--muted);">Nadie recibe avisos todavía.</td></tr>'
    : _chatsTelegram.map(c =>
        `<tr><td>${c.nombre}</td><td>${c.chat_id}</td><td>${(c.agregado_en || '').slice(0,10)}</td>` +
        `<td class="acciones"><button type="button" class="btn-link btnQuitarTelegram" data-chat="${c.chat_id}">Quitar</button></td></tr>`
      ).join('');
  await cargarSelectUsuariosTelegram();
}

async function cargarSelectUsuariosTelegram() {
  const enlazados = new Set(_chatsTelegram.filter(c => c.usuario_id).map(c => c.usuario_id));
  const disponibles = _usuarios.filter(u => !enlazados.has(u.id));
  const select = document.getElementById('usuarioTelegram');
  if (disponibles.length === 0) {
    select.innerHTML = '<option value="">(todos los usuarios ya tienen Telegram enlazado)</option>';
    document.getElementById('btnInvitar').disabled = true;
    return;
  }
  document.getElementById('btnInvitar').disabled = false;
  select.innerHTML = disponibles.map(u => `<option value="${u.id}">${u.nombre} (${u.username})</option>`).join('');
}

async function cargarHistorial() {
  const r = await fetch('/api/historial-config');
  if (r.status !== 200) return;
  const d = await r.json();
  document.getElementById('seccionHistorial').style.display = 'block';
  const ETIQUETAS_TIPO = { vida_util: 'Vida útil', maquinas: 'Máquinas' };
  document.querySelector('#tablaHistorial tbody').innerHTML = d.length === 0
    ? '<tr><td colspan="4" style="color:var(--muted);">Sin cambios registrados todavía.</td></tr>'
    : d.map(h => `
        <tr>
          <td>${(h.fecha || '').replace('T', ' ').slice(0, 16)}</td>
          <td>${h.usuario || '—'}</td>
          <td>${ETIQUETAS_TIPO[h.tipo] || h.tipo} · ${h.codigo}${h.clave_cliente ? ' · ' + h.clave_cliente : ''}</td>
          <td>${h.valor}</td>
        </tr>
      `).join('');
}

async function iniciar() {
  await cargarUsuarios();
  await verificarRol();
  await cargarChatsTelegram();
  if (_esAdmin) await cargarHistorial();
}
iniciar();

document.getElementById('btnMostrarCrear').addEventListener('click', () => {
  document.getElementById('cajaCrear').style.display = 'block';
  document.getElementById('btnMostrarCrear').style.display = 'none';
});
document.getElementById('btnCancelarCrear').addEventListener('click', () => {
  document.getElementById('cajaCrear').style.display = 'none';
  document.getElementById('btnMostrarCrear').style.display = 'inline-block';
});

document.getElementById('btnCrear').addEventListener('click', async () => {
  const nombre = document.getElementById('nombre').value.trim();
  const username = document.getElementById('username').value.trim();
  const password = document.getElementById('password').value;
  const rol = document.getElementById('rol').value;
  const msg = document.getElementById('mensaje');
  msg.className = 'mensaje';
  msg.textContent = '';
  if (!nombre || !username || !password) {
    msg.textContent = 'Llena todos los campos.';
    msg.classList.add('error');
    return;
  }
  const motivoPassword = motivoPasswordInvalida(password);
  if (motivoPassword) {
    msg.textContent = motivoPassword;
    msg.classList.add('error');
    return;
  }
  const r = await fetch('/api/usuarios', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ nombre, username, password, rol }),
  });
  const d = await r.json();
  if (d.error) {
    msg.textContent = 'Error: ' + d.error;
    msg.classList.add('error');
    return;
  }
  msg.textContent = 'Usuario creado.';
  msg.classList.add('ok');
  document.getElementById('nombre').value = '';
  document.getElementById('username').value = '';
  document.getElementById('password').value = '';
  await cargarUsuarios();
  await cargarSelectUsuariosTelegram();
});

document.querySelector('#tablaUsuarios tbody').addEventListener('click', async (e) => {
  const btnCambiar = e.target.closest('.btn-cambiar-password');
  if (btnCambiar) {
    const fila = btnCambiar.closest('tr');
    abrirFormPassword(fila, btnCambiar.dataset.id, btnCambiar.dataset.nombre);
    return;
  }
  const btnCancelar = e.target.closest('.btn-cancelar-password');
  if (btnCancelar) {
    cerrarFormsPassword();
    return;
  }
  const btnGuardar = e.target.closest('.btn-guardar-password');
  if (btnGuardar) {
    const contenedor = btnGuardar.closest('.form-password-inline');
    const nueva = contenedor.querySelector('.input-password-nueva').value;
    const confirmar = contenedor.querySelector('.input-password-confirmar').value;
    const msg = btnGuardar.closest('td').querySelector('.mensaje-password-inline');
    msg.className = 'mensaje mensaje-password-inline';
    msg.textContent = '';
    if (!nueva || !confirmar) {
      msg.textContent = 'Llena los dos campos.';
      msg.classList.add('error');
      return;
    }
    if (nueva !== confirmar) {
      msg.textContent = 'No coinciden.';
      msg.classList.add('error');
      return;
    }
    const motivo = motivoPasswordInvalida(nueva);
    if (motivo) {
      msg.textContent = motivo;
      msg.classList.add('error');
      return;
    }
    btnGuardar.disabled = true;
    btnGuardar.textContent = 'Guardando...';
    const r = await fetch(`/api/usuarios/${btnGuardar.dataset.id}/password`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password_nueva: nueva }),
    });
    const d = await r.json();
    if (d.error) {
      msg.textContent = 'Error: ' + d.error;
      msg.classList.add('error');
      btnGuardar.disabled = false;
      btnGuardar.textContent = 'Guardar';
      return;
    }
    msg.textContent = 'Contraseña cambiada.';
    msg.classList.add('ok');
    setTimeout(cerrarFormsPassword, 1200);
  }
});

document.getElementById('btnInvitar').addEventListener('click', async () => {
  const usuarioId = parseInt(document.getElementById('usuarioTelegram').value, 10);
  const msg = document.getElementById('mensajeTelegram');
  msg.className = 'mensaje';
  msg.textContent = '';
  document.getElementById('cajaLink').style.display = 'none';
  if (!usuarioId) {
    msg.textContent = 'Elige un usuario.';
    msg.classList.add('error');
    return;
  }
  const r = await fetch('/api/telegram/invitar', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ usuario_id: usuarioId }),
  });
  const d = await r.json();
  if (d.error) {
    msg.textContent = 'Error: ' + d.error;
    msg.classList.add('error');
    return;
  }
  msg.textContent = 'Link generado para ' + d.nombre + '.';
  msg.classList.add('ok');
  document.getElementById('linkGenerado').value = d.link;
  document.getElementById('cajaLink').style.display = 'block';
});

document.getElementById('btnCopiarLink').addEventListener('click', async () => {
  const input = document.getElementById('linkGenerado');
  input.select();
  try {
    await navigator.clipboard.writeText(input.value);
  } catch (e) {
    document.execCommand('copy');
  }
});

document.querySelector('#tablaTelegram tbody').addEventListener('click', async (e) => {
  const btn = e.target.closest('.btnQuitarTelegram');
  if (!btn) return;
  if (!confirm('¿Quitar este destinatario de los avisos?')) return;
  await fetch('/api/telegram/chats/' + encodeURIComponent(btn.dataset.chat), { method: 'DELETE' });
  cargarChatsTelegram();
});
