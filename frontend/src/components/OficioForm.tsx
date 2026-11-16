import { useState, type FormEvent } from "react";
import { api, errorMessage, ApiError } from "../api";
import type { Config, Oficio, Person, Semaphore } from "../types";
import {
  addBusinessDays,
  normalized,
  personForNumber,
  semaphore,
  termDays,
} from "../model/operations.mjs";
import { safeRandomUUID } from "../utils/uuid";
import { Badge } from "./Badge";
import { Modal } from "./Modal";

const termChoices = [
  ["SIN_PLAZO", "Sin plazo"],
  ["HORAS_24", "24h"],
  ["DIAS_HABILES_2", "2d"],
  ["DIAS_HABILES_3", "3d"],
  ["DIAS_HABILES_5", "5d"],
  ["DIAS_HABILES_10", "10d"],
  ["FECHA_FIJA", "Fecha fija"],
];

export function OficioForm({
  config,
  people,
  nextFolio,
  record,
  onClose,
  onSaved,
}: {
  config: Config;
  people: Person[];
  nextFolio: string;
  record?: Oficio;
  onClose: () => void;
  onSaved: (record: Oficio) => void;
}) {
  const [form, setForm] = useState({
    numero_oficio: record?.numero_oficio || "",
    fecha_oficio: record?.fecha_oficio || config.today,
    fecha_recepcion: record?.fecha_recepcion || config.today,
    naturaleza: record?.naturaleza || "ORIGINAL",
    requiere_respuesta: record?.requiere_respuesta ?? true,
    plazo_tipo: record?.plazo_tipo || "SIN_PLAZO",
    fecha_limite_respuesta: record?.fecha_limite_respuesta || "",
    dirigido_nombre:
      record?.dirigido_nombre || "ARQ. MARTHA MARGARITA REYNÉS NOGUERA",
    dirigido_cargo:
      record?.dirigido_cargo || "SUBDIRECTORA DE SERVICIOS GENERALES",
    firmante_nombre: record?.firmante_nombre || "",
    firmante_cargo: record?.firmante_cargo || "",
    asunto: record?.asunto || "",
    area_asignada: record?.area_asignada || "SSG",
    responsables_detalle: record?.responsables_detalle || "",
    observaciones_fisicas: record?.observaciones_fisicas || "ORIGINAL",
  });
  const [copies, setCopies] = useState(
    (record?.copias_dirigido_json || []).map((copy) => ({
      ...copy,
      key: safeRandomUUID(),
    })),
  );
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<Oficio | null>(null);
  const set = <K extends keyof typeof form>(key: K, value: (typeof form)[K]) =>
    setForm((previous) => ({ ...previous, [key]: value }));
  const days = termDays[form.plazo_tipo as keyof typeof termDays];
  const deadline =
    form.requiere_respuesta && form.fecha_recepcion
      ? days
        ? addBusinessDays(form.fecha_recepcion, days)
        : form.plazo_tipo === "FECHA_FIJA"
          ? form.fecha_limite_respuesta
          : null
      : null;
  const live = semaphore(
    {
      ...form,
      fecha_limite_respuesta: deadline,
      estatus_atencion: form.requiere_respuesta ? "PENDIENTE" : "CONOCIMIENTO",
    },
    config.today,
  ) as Semaphore;
  function personChange(kind: "firmante" | "dirigido", value: string) {
    const person = people.find(
      (p) => normalized(p.nombre_mostrar) === normalized(value),
    );
    setForm((previous) => ({
      ...previous,
      [`${kind}_nombre`]: value,
      [`${kind}_cargo`]: person?.cargo || "",
    }));
  }
  function numberChange(value: string) {
    const person = personForNumber(value, people) as Person | null;
    setForm((previous) => ({
      ...previous,
      numero_oficio: value,
      ...(person
        ? {
            firmante_nombre: person.nombre_mostrar,
            firmante_cargo: person.cargo,
          }
        : {}),
    }));
  }
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const payload = {
      ...form,
      fecha_limite_respuesta: deadline,
      copias_dirigido_json: copies.map(({ nombre, cargo }) => ({
        nombre,
        cargo,
      })),
      ...(record
        ? { version: record.version }
        : {
            anio: 2026,
            estatus_atencion: form.requiere_respuesta
              ? "PENDIENTE"
              : "CONOCIMIENTO",
          }),
    };
    try {
      onSaved(
        await api<Oficio>(record ? `/oficios/${record.id}` : "/oficios", {
          method: record ? "PATCH" : "POST",
          body: JSON.stringify(payload),
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
      if (err instanceof ApiError && err.status === 409 && err.current)
        setConflict(err.current as Oficio);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      title={record ? `Editar ${record.folio_ssg}` : "Nuevo oficio"}
      onClose={onClose}
      wide
    >
      <form onSubmit={submit}>
        <div className="modal-content">
          <div className="capture-banner">
            <div>
              <span className="eyebrow">
                {record ? "EXPEDIENTE" : "SIGUIENTE FOLIO"}
              </span>
              <strong className="mono">{record?.folio_ssg || nextFolio}</strong>
            </div>
            <p>
              {record
                ? `Versión ${record.version}`
                : "El folio definitivo se asigna al guardar."}
            </p>
          </div>
          {error && (
            <div role="alert" className="error-box">
              {error}
              {conflict && (
                <p>
                  Versión actual:{" "}
                  <span className="mono">{conflict.version}</span>. Asunto
                  actual: {conflict.asunto}. Sus datos permanecen en este
                  formulario.
                </p>
              )}
            </div>
          )}
          <div className="section-label">01 / RECEPCIÓN</div>
          <div className="form-grid">
            <label className="span-2">
              Número de oficio
              <input
                className="mono"
                autoFocus
                required
                maxLength={250}
                value={form.numero_oficio}
                onChange={(e) => numberChange(e.target.value)}
                placeholder="Ej. UA/DRM/10-11/01/2026"
              />
            </label>
            <label>
              Fecha del oficio
              <input
                className="mono"
                type="date"
                required
                value={form.fecha_oficio}
                onChange={(e) => set("fecha_oficio", e.target.value)}
              />
            </label>
            <label>
              Fecha de recepción
              <input
                className="mono"
                type="date"
                required
                value={form.fecha_recepcion}
                onChange={(e) => set("fecha_recepcion", e.target.value)}
              />
            </label>
          </div>
          <div
            className="classification"
            role="group"
            aria-label="Clasificación"
          >
            <button
              type="button"
              aria-label="ORIGINAL Requiere atención"
              aria-pressed={form.naturaleza === "ORIGINAL"}
              onClick={() =>
                setForm((p) => ({
                  ...p,
                  naturaleza: "ORIGINAL",
                  requiere_respuesta: true,
                  observaciones_fisicas: "ORIGINAL",
                }))
              }
            >
              <strong>ORIGINAL</strong>
              <span>Requiere atención</span>
            </button>
            <button
              type="button"
              aria-label="CC Para conocimiento"
              aria-pressed={form.naturaleza === "CC"}
              onClick={() =>
                setForm((p) => ({
                  ...p,
                  naturaleza: "CC",
                  requiere_respuesta: false,
                  plazo_tipo: "SIN_PLAZO",
                  observaciones_fisicas: "CC",
                }))
              }
            >
              <strong>CC</strong>
              <span>Para conocimiento</span>
            </button>
          </div>
          {form.naturaleza === "CC" && (
            <label className="check-label">
              <input
                type="checkbox"
                checked={form.requiere_respuesta}
                onChange={(e) => set("requiere_respuesta", e.target.checked)}
              />
              Esta copia también requiere respuesta
            </label>
          )}
          {form.requiere_respuesta && (
            <>
              <span className="field-title">
                Plazo de atención · días hábiles
              </span>
              <div
                className="term-chips"
                role="group"
                aria-label="Plazo de atención"
              >
                {termChoices.map(([value, label]) => (
                  <button
                    className="mono"
                    type="button"
                    key={value}
                    aria-pressed={form.plazo_tipo === value}
                    onClick={() => set("plazo_tipo", value)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {form.plazo_tipo === "FECHA_FIJA" && (
                <label>
                  Fecha límite
                  <input
                    className="mono"
                    type="date"
                    required
                    value={form.fecha_limite_respuesta}
                    onChange={(e) =>
                      set("fecha_limite_respuesta", e.target.value)
                    }
                  />
                </label>
              )}
            </>
          )}
          <div className="deadline-preview">
            <Badge value={live} />
            <span>
              Fecha límite:{" "}
              <strong className="mono">{deadline || "Por definir"}</strong>
            </span>
          </div>
          <p className="field-help">
            Cómputo de lunes a viernes. 24h equivale a un día hábil, según el
            criterio operativo.
          </p>
          <div className="section-label">02 / ORIGEN Y DESTINATARIO</div>
          <datalist id="people-list">
            {people.map((p) => (
              <option key={p.id} value={p.nombre_mostrar}>
                {p.cargo}
              </option>
            ))}
          </datalist>
          <div className="form-grid">
            <label>
              Firmante
              <input
                list="people-list"
                value={form.firmante_nombre}
                onChange={(e) => personChange("firmante", e.target.value)}
              />
            </label>
            <label>
              Cargo del firmante
              <input
                value={form.firmante_cargo}
                onChange={(e) => set("firmante_cargo", e.target.value)}
              />
            </label>
            <label>
              Dirigido a
              <input
                list="people-list"
                value={form.dirigido_nombre}
                onChange={(e) => personChange("dirigido", e.target.value)}
              />
            </label>
            <label>
              Cargo del destinatario
              <input
                value={form.dirigido_cargo}
                onChange={(e) => set("dirigido_cargo", e.target.value)}
              />
            </label>
          </div>
          {copies.map((copy, index) => (
            <div key={copy.key} className="copy-row">
              <label>
                Co-destinatario {index + 1}
                <input
                  value={copy.nombre}
                  required
                  onChange={(e) =>
                    setCopies((list) =>
                      list.map((p) =>
                        p.key === copy.key
                          ? { ...p, nombre: e.target.value }
                          : p,
                      ),
                    )
                  }
                />
              </label>
              <label>
                Cargo
                <input
                  value={copy.cargo}
                  onChange={(e) =>
                    setCopies((list) =>
                      list.map((p) =>
                        p.key === copy.key
                          ? { ...p, cargo: e.target.value }
                          : p,
                      ),
                    )
                  }
                />
              </label>
              <button
                className="text-button"
                type="button"
                onClick={() =>
                  setCopies((list) => list.filter((p) => p.key !== copy.key))
                }
              >
                Quitar
              </button>
            </div>
          ))}
          <button
            className="text-button"
            type="button"
            onClick={() =>
              setCopies((list) => [
                ...list,
                { key: safeRandomUUID(), nombre: "", cargo: "" },
              ])
            }
          >
            + Agregar co-destinatario
          </button>
          <div className="section-label">03 / ASUNTO Y TURNO</div>
          <label>
            Asunto
            <textarea
              required
              rows={3}
              maxLength={20000}
              value={form.asunto}
              onChange={(e) => set("asunto", e.target.value)}
            />
          </label>
          <div className="form-grid">
            <label>
              Área responsable
              <select
                value={form.area_asignada}
                onChange={(e) => set("area_asignada", e.target.value)}
              >
                {config.areas.map((area) => (
                  <option key={area.clave} value={area.clave}>
                    {area.clave} · {area.nombre}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Responsable / analista
              <input
                list="analysts"
                value={form.responsables_detalle}
                onChange={(e) => set("responsables_detalle", e.target.value)}
              />
              <datalist id="analysts">
                {config.areas
                  .flatMap((a) => a.analistas_sugeridos_json)
                  .filter((a, i, all) => all.indexOf(a) === i)
                  .map((a) => (
                    <option key={a}>{a}</option>
                  ))}
              </datalist>
            </label>
          </div>
          <label>
            Observaciones físicas
            <input
              value={form.observaciones_fisicas}
              onChange={(e) => set("observaciones_fisicas", e.target.value)}
            />
          </label>
        </div>
        <div className="modal-foot">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button
            className="button primary"
            disabled={busy || Boolean(conflict)}
          >
            {busy
              ? "Guardando…"
              : record
                ? "Guardar cambios"
                : "Registrar oficio"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
