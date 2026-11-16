from datetime import UTC, date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, String, Text, false, true
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utcnow():
    return datetime.now(UTC).replace(tzinfo=None)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40))
    area: Mapped[str] = mapped_column(String(10), default="SSG", server_default="SSG")
    display_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())


class Funcionario(Base):
    __tablename__ = "funcionarios_directorio"
    id: Mapped[int] = mapped_column(primary_key=True)
    nombre_normalizado: Mapped[str] = mapped_column(String(250), unique=True, index=True)
    nombre_mostrar: Mapped[str] = mapped_column(String(250), default="", server_default="")
    cargo: Mapped[str] = mapped_column(String(500), default="", server_default="")
    dependencia_unidad: Mapped[str] = mapped_column(String(500), default="", server_default="")
    prefijo_oficio_frecuente: Mapped[str] = mapped_column(
        String(150), default="", server_default=""
    )
    es_interno: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    activo: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    __mapper_args__ = {"version_id_col": version}


class Area(Base):
    __tablename__ = "areas_responsables"
    id: Mapped[int] = mapped_column(primary_key=True)
    clave: Mapped[str] = mapped_column(String(10), unique=True)
    nombre: Mapped[str] = mapped_column(String(200), default="", server_default="")
    titular_nombre: Mapped[str] = mapped_column(String(250), default="", server_default="")
    analistas_sugeridos_json: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")


class Counter(Base):
    __tablename__ = "counters"
    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Oficio(Base):
    __tablename__ = "oficios"
    id: Mapped[int] = mapped_column(primary_key=True)
    anio: Mapped[int] = mapped_column(Integer, default=2026, server_default="2026")
    folio_ssg: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    consecutivo_anual: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    numero_oficio: Mapped[str] = mapped_column(String(250), index=True)
    fecha_oficio: Mapped[date | None] = mapped_column(Date)
    fecha_recepcion: Mapped[date | None] = mapped_column(Date)
    naturaleza: Mapped[str] = mapped_column(
        String(15), default="ORIGINAL", server_default="ORIGINAL"
    )
    requiere_respuesta: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    plazo_tipo: Mapped[str] = mapped_column(
        String(30), default="SIN_PLAZO", server_default="SIN_PLAZO"
    )
    plazo_dias_habiles: Mapped[int | None] = mapped_column(Integer)
    fecha_limite_respuesta: Mapped[date | None] = mapped_column(Date)
    dirigido_nombre: Mapped[str] = mapped_column(String(500), default="", server_default="")
    dirigido_cargo: Mapped[str] = mapped_column(String(500), default="", server_default="")
    copias_dirigido_json: Mapped[list] = mapped_column(JSON, default=list, server_default="[]")
    firmante_nombre: Mapped[str] = mapped_column(String(500), default="", server_default="")
    firmante_cargo: Mapped[str] = mapped_column(String(500), default="", server_default="")
    asunto: Mapped[str] = mapped_column(Text, default="", server_default="")
    area_asignada: Mapped[str] = mapped_column(
        String(10), default="SSG", server_default="SSG", index=True
    )
    responsables_detalle: Mapped[str] = mapped_column(String(500), default="", server_default="")
    observaciones_fisicas: Mapped[str] = mapped_column(Text, default="", server_default="")
    tiene_documento_entrada: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    documento_entrada_nombre: Mapped[str | None] = mapped_column(String(500))
    documento_entrada_ruta: Mapped[str | None] = mapped_column(Text)
    estatus_atencion: Mapped[str] = mapped_column(
        String(25), default="PENDIENTE", server_default="PENDIENTE", index=True
    )
    nota_atencion: Mapped[str | None] = mapped_column(Text)
    oficio_respuesta_numero: Mapped[str | None] = mapped_column(String(500))
    fecha_atencion: Mapped[date | None] = mapped_column(Date)
    tiene_acuse_respuesta: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    acuse_respuesta_nombre: Mapped[str | None] = mapped_column(String(500))
    acuse_respuesta_ruta: Mapped[str | None] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, server_default="1970-01-01 00:00:00"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow, server_default="1970-01-01 00:00:00"
    )
    __table_args__ = (Index("ix_oficios_fecha_limite", "fecha_limite_respuesta"),)
    __mapper_args__ = {"version_id_col": version}


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    actor_username: Mapped[str] = mapped_column(String(80))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[str] = mapped_column(String(100), index=True)
    action: Mapped[str] = mapped_column(String(50))
    before_json: Mapped[dict | None] = mapped_column(JSON)
    after_json: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64), unique=True)
    source_name: Mapped[str] = mapped_column(String(250))
    summary: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
