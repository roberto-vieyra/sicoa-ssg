import assert from "node:assert/strict";
import test from "node:test";
import {
  addBusinessDays,
  businessDaysBetween,
  normalized,
  personForNumber,
  semaphore,
} from "../src/model/operations.mjs";

test("días hábiles cruzan fines de semana y año sin zona horaria local", () => {
  assert.equal(addBusinessDays("2026-11-06", 1), "2026-11-09");
  assert.equal(addBusinessDays("2026-12-31", 2), "2027-01-04");
  assert.equal(addBusinessDays("2026-11-06", 7), "2026-11-17");
  assert.equal(businessDaysBetween("2026-11-09", "2026-11-06"), -1);
  assert.throws(() => addBusinessDays("2026-02-31", 2));
  assert.throws(() => addBusinessDays("2026-11-06", -1));
});
test("límites de semáforo y precedencia de cancelación y atención", () => {
  const base = {
    naturaleza: "ORIGINAL",
    requiere_respuesta: true,
    estatus_atencion: "PENDIENTE",
    fecha_limite_respuesta: "2026-11-12",
  };
  assert.equal(semaphore(base, "2026-11-10").codigo, "AMBAR_POR_VENCER");
  assert.equal(
    semaphore({ ...base, fecha_limite_respuesta: "2026-11-13" }, "2026-11-10")
      .codigo,
    "VERDE_EN_TIEMPO",
  );
  assert.equal(
    semaphore({ ...base, fecha_limite_respuesta: null }, "2026-11-10").etiqueta,
    "PENDIENTE DE PLAZO",
  );
  assert.equal(
    semaphore({ ...base, estatus_atencion: "ATENDIDO" }, "2026-11-30").codigo,
    "AZUL_ATENDIDO",
  );
  assert.equal(
    semaphore({ ...base, estatus_atencion: "CANCELADO" }, "2026-11-30").codigo,
    "GRIS_INFORMATIVO",
  );
});
test("prefijos ambiguos no seleccionan un firmante incorrecto", () => {
  const people = [
    { nombre_mostrar: "A", prefijo_oficio_frecuente: "UA/" },
    { nombre_mostrar: "B", prefijo_oficio_frecuente: "UA/DRM/" },
  ];
  assert.equal(personForNumber("UA/DRM/12", people).nombre_mostrar, "B");
  assert.equal(
    personForNumber("UA/DRM/12", [
      ...people,
      { nombre_mostrar: "C", prefijo_oficio_frecuente: "UA/DRM/" },
    ]),
    null,
  );
  assert.equal(normalized("  ReynÉs   Noguera "), "REYNES NOGUERA");
});
