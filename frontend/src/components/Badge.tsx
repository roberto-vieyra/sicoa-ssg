import type { Semaphore } from "../types";

export function Badge({ value }: { value: Semaphore }) {
  return (
    <span className={`badge ${value.codigo.toLowerCase()}`}>
      <span className="status-dot" />
      {value.etiqueta}
    </span>
  );
}
