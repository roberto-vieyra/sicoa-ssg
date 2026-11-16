export const termDays = {
  HORAS_24: 1,
  DIAS_HABILES_2: 2,
  DIAS_HABILES_3: 3,
  DIAS_HABILES_5: 5,
  DIAS_HABILES_10: 10,
};

function parseDate(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) throw new Error("Fecha inválida");
  const result = new Date(`${value}T12:00:00Z`);
  if (
    Number.isNaN(result.getTime()) ||
    result.toISOString().slice(0, 10) !== value
  )
    throw new Error("Fecha inválida");
  return result;
}

export function addBusinessDays(start, count) {
  if (!Number.isInteger(count) || count < 0) throw new Error("Plazo inválido");
  const day = parseDate(start);
  while (count) {
    day.setUTCDate(day.getUTCDate() + 1);
    if (![0, 6].includes(day.getUTCDay())) count--;
  }
  return day.toISOString().slice(0, 10);
}

export function businessDaysBetween(start, end) {
  if (end < start) return -businessDaysBetween(end, start);
  const day = parseDate(start);
  const final = parseDate(end);
  let count = 0;
  while (day < final) {
    day.setUTCDate(day.getUTCDate() + 1);
    if (![0, 6].includes(day.getUTCDay())) count++;
  }
  return count;
}

export function semaphore(record, reference) {
  const result = (codigo, etiqueta, dias_habiles = null) => ({
    codigo,
    etiqueta,
    dias_habiles,
  });
  if (record.estatus_atencion === "CANCELADO")
    return result("GRIS_INFORMATIVO", "CANCELADO");
  if (record.estatus_atencion === "ATENDIDO")
    return result("AZUL_ATENDIDO", "ATENDIDO");
  if (!record.requiere_respuesta)
    return result(
      "GRIS_INFORMATIVO",
      record.naturaleza === "CC" ? "INFORMATIVO / CC" : "INFORMATIVO",
    );
  if (!record.fecha_limite_respuesta)
    return result("AMBAR_POR_VENCER", "PENDIENTE DE PLAZO");
  const days = businessDaysBetween(reference, record.fecha_limite_respuesta);
  if (record.fecha_limite_respuesta < reference)
    return result("ROJO_VENCIDO", "VENCIDO", days);
  return days <= 2
    ? result("AMBAR_POR_VENCER", "POR VENCER", days)
    : result("VERDE_EN_TIEMPO", "EN TIEMPO", days);
}

export function normalized(value) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/\s+/g, " ")
    .trim()
    .toUpperCase();
}

export function personForNumber(number, people) {
  const matches = people.filter(
    (p) =>
      p.prefijo_oficio_frecuente &&
      normalized(number).startsWith(normalized(p.prefijo_oficio_frecuente)),
  );
  matches.sort(
    (a, b) =>
      b.prefijo_oficio_frecuente.length - a.prefijo_oficio_frecuente.length,
  );
  if (!matches.length) return null;
  const best = matches.filter(
    (p) =>
      p.prefijo_oficio_frecuente.length ===
      matches[0].prefijo_oficio_frecuente.length,
  );
  return best.length === 1 ? best[0] : null;
}
