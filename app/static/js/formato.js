// Formato de numeros, moneda y fechas (las fechas "solo dia" se leen como dia local).
const esc = (t) => String(t ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const fmt = new Intl.NumberFormat('es-MX');
// Cada venta se muestra en la moneda real con la que se facturó (el backend
// ya no convierte nada): si fue en dólares se ve en dólares, si fue en
// pesos se ve en pesos. Siempre con la clave de moneda explícita al final.
const fmtMoney = (valor, moneda) => {
  const m = moneda || 'MXN';
  const simbolo = m === 'USD' ? 'US$' : '$';
  return `${simbolo}${fmt.format(Math.round(valor || 0))} ${m}`;
};
// "2026-10-15" (solo fecha) hay que leerla como dia LOCAL: new Date("2026-10-15") la toma como
// medianoche UTC y en Mexico se veria como el 14.
const parseFecha = (iso) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso || '');
  return m ? new Date(+m[1], +m[2] - 1, +m[3]) : new Date(iso);
};
const fmtFecha = (iso) => parseFecha(iso).toLocaleDateString('es-MX', { year: 'numeric', month: 'short', day: 'numeric' });
const estaVencido = (iso) => !!iso && parseFecha(iso) < new Date();

const dentroDeUnaSemana = (iso) => {
  if (!iso) return false;
  const hoy = new Date();
  const limite = new Date();
  limite.setDate(limite.getDate() + 7);
  const fecha = parseFecha(iso);
  return fecha >= hoy && fecha <= limite;
};
