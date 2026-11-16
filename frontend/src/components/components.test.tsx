import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Badge } from "./Badge";
import { OficioForm } from "./OficioForm";
import type { Config, Person } from "../types";
import { semaphore } from "../model/operations.mjs";

const config: Config = {
  today: "2026-11-10",
  timezone: "America/Mexico_City",
  business_calendar: "lunes a viernes",
  areas: [
    {
      clave: "SSG",
      nombre: "SSG",
      titular_nombre: "",
      analistas_sugeridos_json: ["MARIO"],
    },
  ],
};
const people: Person[] = [
  {
    id: 1,
    nombre_mostrar: "JOSE PEREZ",
    nombre_normalizado: "JOSE PEREZ",
    cargo: "DIRECTOR",
    dependencia_unidad: "",
    prefijo_oficio_frecuente: "UF/DC/",
    es_interno: true,
    activo: true,
    version: 1,
  },
];

describe("captura por excepción", () => {
  it("muestra el siguiente folio, calcula plazo y clasifica CC", () => {
    render(
      <OficioForm
        config={config}
        people={people}
        nextFolio="SSG963"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );
    expect(screen.getByText("SSG963")).toBeInTheDocument();
    expect(screen.getByLabelText("Fecha de recepción")).toHaveValue(
      "2026-11-10",
    );
    fireEvent.click(screen.getByText("3d", { selector: "button" }));
    expect(screen.getByText("2026-11-13")).toBeInTheDocument();
    expect(screen.getByText("EN TIEMPO")).toBeInTheDocument();
    fireEvent.click(
      screen.getByLabelText("CC Para conocimiento", { selector: "button" }),
    );
    expect(screen.getByText("INFORMATIVO / CC")).toBeInTheDocument();
    expect(
      screen.queryByText("3d", { selector: "button" }),
    ).not.toBeInTheDocument();
  });
  it("autocompleta cargo por nombre y prefijo sin bloquear edición", () => {
    render(
      <OficioForm
        config={config}
        people={people}
        nextFolio="SSG963"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );
    fireEvent.change(screen.getByLabelText("Número de oficio"), {
      target: { value: "UF/DC/123" },
    });
    expect(screen.getByLabelText("Firmante")).toHaveValue("JOSE PEREZ");
    expect(screen.getByLabelText("Cargo del firmante")).toHaveValue("DIRECTOR");
    fireEvent.change(screen.getByLabelText("Cargo del firmante"), {
      target: { value: "DIRECTOR ENCARGADO" },
    });
    expect(screen.getByLabelText("Cargo del firmante")).toHaveValue(
      "DIRECTOR ENCARGADO",
    );
  });
  it("expresa el semáforo con texto accesible además de color", () => {
    render(
      <Badge
        value={{
          codigo: "ROJO_VENCIDO",
          etiqueta: "VENCIDO",
          dias_habiles: -2,
        }}
      />,
    );
    expect(screen.getByText("VENCIDO")).toHaveClass("rojo_vencido");
  });
  it("calcula el vencimiento y prioriza cierre", () => {
    const record = {
      estatus_atencion: "PENDIENTE",
      requiere_respuesta: true,
      naturaleza: "ORIGINAL",
      fecha_limite_respuesta: "2026-11-09",
    };
    expect(semaphore(record, "2026-11-10")).toMatchObject({
      codigo: "ROJO_VENCIDO",
      dias_habiles: -1,
    });
    expect(
      semaphore({ ...record, estatus_atencion: "ATENDIDO" }, "2026-11-10"),
    ).toMatchObject({ codigo: "AZUL_ATENDIDO" });
  });
});
