from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from backend.app.services.calendar import PLAZOS, add_business_days

AreaKey = Literal["SSG", "GAI", "GSA", "DRM", "SA"]
Status = Literal["PENDIENTE", "EN_SEGUIMIENTO", "ATENDIDO", "CONOCIMIENTO", "CANCELADO"]
Term = Literal[
    "SIN_PLAZO",
    "HORAS_24",
    "DIAS_HABILES_2",
    "DIAS_HABILES_3",
    "DIAS_HABILES_5",
    "DIAS_HABILES_10",
    "FECHA_FIJA",
]


class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Login(InputModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class CopyRecipient(InputModel):
    nombre: str = Field(min_length=1, max_length=500)
    cargo: str = Field(default="", max_length=500)


class OficioCreate(InputModel):
    anio: int = Field(default=2026, ge=2000, le=2100)
    numero_oficio: str = Field(min_length=1, max_length=250)
    fecha_oficio: date
    fecha_recepcion: date
    naturaleza: Literal["ORIGINAL", "CC"] = "ORIGINAL"
    requiere_respuesta: bool = True
    plazo_tipo: Term = "SIN_PLAZO"
    plazo_dias_habiles: int | None = Field(default=None, ge=1, le=365)
    fecha_limite_respuesta: date | None = None
    dirigido_nombre: str = Field(default="", max_length=500)
    dirigido_cargo: str = Field(default="", max_length=500)
    copias_dirigido_json: list[CopyRecipient] = Field(default_factory=list, max_length=25)
    firmante_nombre: str = Field(default="", max_length=500)
    firmante_cargo: str = Field(default="", max_length=500)
    asunto: str = Field(min_length=1, max_length=20000)
    area_asignada: AreaKey = "SSG"
    responsables_detalle: str = Field(default="", max_length=500)
    observaciones_fisicas: str = Field(default="", max_length=10000)
    estatus_atencion: Status = "PENDIENTE"
    nota_atencion: str | None = Field(default=None, max_length=20000)
    oficio_respuesta_numero: str | None = Field(default=None, max_length=500)
    fecha_atencion: date | None = None

    @model_validator(mode="after")
    def derive_deadline(self):
        if self.estatus_atencion == "CONOCIMIENTO" and self.requiere_respuesta:
            raise ValueError("Un oficio de conocimiento no puede requerir respuesta.")
        if not self.requiere_respuesta:
            self.plazo_tipo = "SIN_PLAZO"
            self.plazo_dias_habiles = None
            self.fecha_limite_respuesta = None
            if self.estatus_atencion in {"PENDIENTE", "EN_SEGUIMIENTO"}:
                self.estatus_atencion = "CONOCIMIENTO"
        elif self.plazo_tipo in PLAZOS:
            self.plazo_dias_habiles = PLAZOS[self.plazo_tipo]
            self.fecha_limite_respuesta = add_business_days(
                self.fecha_recepcion, self.plazo_dias_habiles
            )
        elif self.plazo_tipo == "FECHA_FIJA":
            if not self.fecha_limite_respuesta:
                raise ValueError("La fecha fija requiere una fecha límite.")
        else:
            self.plazo_dias_habiles = None
            self.fecha_limite_respuesta = None
        if self.estatus_atencion == "ATENDIDO" and not self.fecha_atencion:
            raise ValueError("Registrar la atención requiere fecha de atención.")
        return self


class OficioPatch(InputModel):
    version: int = Field(ge=1)
    numero_oficio: str | None = Field(default=None, min_length=1, max_length=250)
    fecha_oficio: date | None = None
    fecha_recepcion: date | None = None
    naturaleza: Literal["ORIGINAL", "CC"] | None = None
    requiere_respuesta: bool | None = None
    plazo_tipo: Term | None = None
    plazo_dias_habiles: int | None = Field(default=None, ge=1, le=365)
    fecha_limite_respuesta: date | None = None
    dirigido_nombre: str | None = Field(default=None, max_length=500)
    dirigido_cargo: str | None = Field(default=None, max_length=500)
    copias_dirigido_json: list[CopyRecipient] | None = Field(default=None, max_length=25)
    firmante_nombre: str | None = Field(default=None, max_length=500)
    firmante_cargo: str | None = Field(default=None, max_length=500)
    asunto: str | None = Field(default=None, min_length=1, max_length=20000)
    area_asignada: AreaKey | None = None
    responsables_detalle: str | None = Field(default=None, max_length=500)
    observaciones_fisicas: str | None = Field(default=None, max_length=10000)
    estatus_atencion: Status | None = None
    nota_atencion: str | None = Field(default=None, max_length=20000)
    oficio_respuesta_numero: str | None = Field(default=None, max_length=500)
    fecha_atencion: date | None = None


class FuncionarioInput(InputModel):
    nombre_mostrar: str = Field(min_length=1, max_length=250)
    cargo: str = Field(default="", max_length=500)
    dependencia_unidad: str = Field(default="", max_length=500)
    prefijo_oficio_frecuente: str = Field(default="", max_length=150)
    es_interno: bool = True
    activo: bool = True


class FuncionarioPatch(InputModel):
    version: int = Field(ge=1)
    nombre_mostrar: str | None = Field(default=None, min_length=1, max_length=250)
    cargo: str | None = Field(default=None, max_length=500)
    dependencia_unidad: str | None = Field(default=None, max_length=500)
    prefijo_oficio_frecuente: str | None = Field(default=None, max_length=150)
    es_interno: bool | None = None
    activo: bool | None = None
