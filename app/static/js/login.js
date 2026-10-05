// Inicio de sesion: muestra el error que manda el servidor en la direccion.
  const params = new URLSearchParams(window.location.search);
  const error = params.get('error');
  if (error === 'bloqueado') {
    const minutos = params.get('minutos') || 'unos';
    document.getElementById('error').textContent =
      `Demasiados intentos fallidos. Espera ${minutos} minuto(s) antes de volver a intentar.`;
    document.getElementById('error').classList.add('activo');
  } else if (error) {
    document.getElementById('error').textContent = 'Usuario o contraseña incorrectos.';
    document.getElementById('error').classList.add('activo');
  }
