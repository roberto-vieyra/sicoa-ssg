import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Oficio } from "../types";
import { Modal } from "./Modal";

export function AttentionForm({
  record,
  today,
  onClose,
  onSaved,
}: {
  record: Oficio;
  today: string;
  onClose: () => void;
  onSaved: (record: Oficio) => void;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    form.set("version", String(record.version));
    const file = form.get("file") as File;
    if (!file?.size) form.delete("file");
    try {
      onSaved(
        await api<Oficio>(`/oficios/${record.id}/atencion`, {
          method: "POST",
          body: form,
        }),
      );
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal title="Registrar atención / Subir acuse" onClose={onClose}>
      <form onSubmit={submit}>
        <div className="modal-content">
          <p className="mono capture-ref">
            {record.folio_ssg} · V{record.version}
          </p>
          <p className="muted">{record.numero_oficio}</p>
          {error && (
            <div role="alert" className="error-box">
              {error}
            </div>
          )}
          <label>
            Nota de atención
            <textarea
              name="nota_atencion"
              autoFocus
              required
              rows={4}
              maxLength={20000}
              placeholder="Describa la gestión realizada y el resultado."
            />
          </label>
          <label>
            Número de oficio de respuesta
            <input
              name="oficio_respuesta_numero"
              className="mono"
              maxLength={500}
            />
          </label>
          <label>
            Fecha de atención
            <input
              type="date"
              name="fecha_atencion"
              required
              defaultValue={today}
              className="mono"
            />
          </label>
          <label className="file-field">
            Acuse de respuesta · PDF
            <input type="file" accept="application/pdf,.pdf" name="file" />
            <span className="field-help">
              Opcional. Hasta 20 MB. Se guardará junto con el cierre del oficio.
            </span>
          </label>
        </div>
        <div className="modal-foot">
          <button type="button" className="button secondary" onClick={onClose}>
            Cancelar
          </button>
          <button className="button primary" disabled={busy}>
            {busy ? "Registrando…" : "Guardar atención y acuse"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
