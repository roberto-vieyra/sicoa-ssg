from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update

from backend.app.db.models import Counter, Oficio, utcnow
from backend.app.schemas import OficioCreate
from backend.app.services.audit import log, snapshot
from backend.app.services.calendar import semaphore


def serialize(record, reference):
    result = snapshot(record)
    if isinstance(record, Oficio):
        result["semaforo"] = semaphore(record, reference)
        result["documento_entrada_disponible"] = bool(
            record.documento_entrada_ruta and record.documento_entrada_ruta.startswith("uploads/")
        )
        result["acuse_respuesta_disponible"] = bool(
            record.acuse_respuesta_ruta and record.acuse_respuesta_ruta.startswith("uploads/")
        )
        # La API pública no expone rutas del equipo de origen.
        result.pop("documento_entrada_ruta", None)
        result.pop("acuse_respuesta_ruta", None)
    return result


def conflict(session, model, record_id, reference):
    session.rollback()
    current = session.get(model, record_id)
    raise HTTPException(
        409,
        {
            "message": "Otro usuario modificó este registro. Recargue y revise sus cambios.",
            "current": serialize(current, reference) if current else None,
        },
    )


def mutate(session, record, expected_version, changes, actor, action, reference):
    before = snapshot(record)
    model, record_id = type(record), record.id
    if record.version != expected_version:
        conflict(session, model, record_id, reference)
    changes["version"] = expected_version + 1
    if isinstance(record, Oficio):
        changes["updated_at"] = utcnow()
    result = session.execute(
        update(model)
        .where(model.id == record_id, model.version == expected_version)
        .values(**changes)
        .execution_options(synchronize_session=False)
    )
    if result.rowcount != 1:
        conflict(session, model, record_id, reference)
    session.expire(record)
    log(session, actor, record, action, before=before)
    return record


def create_oficio(session, data: OficioCreate, actor):
    number = session.scalar(
        update(Counter)
        .where(Counter.key == "folio")
        .values(value=Counter.value + 1)
        .returning(Counter.value)
    )
    if number is None or number > 9999:
        raise HTTPException(409, "Se agotó el rango de folios SSG001 a SSG9999.")
    year_key = f"anio:{data.anio}"
    counter = session.get(Counter, year_key)
    if counter is None:
        # El bloqueo del contador global serializa también el alta del contador anual.
        session.add(Counter(key=year_key, value=0))
        session.flush()
    consecutive = session.scalar(
        update(Counter)
        .where(Counter.key == year_key)
        .values(value=Counter.value + 1)
        .returning(Counter.value)
    )
    record = Oficio(
        **data.model_dump(), folio_ssg=f"SSG{number:03d}", consecutivo_anual=consecutive
    )
    session.add(record)
    session.flush()
    log(session, actor, record, "CREACION")
    return record


def validate_patch(record, changes):
    # Los documentos históricos pueden carecer de fechas. Un cierre no las inventa.
    rule_fields = {
        "fecha_recepcion",
        "naturaleza",
        "requiere_respuesta",
        "plazo_tipo",
        "fecha_limite_respuesta",
        "plazo_dias_habiles",
    }
    if rule_fields.intersection(changes):
        merged = {key: getattr(record, key) for key in OficioCreate.model_fields}
        merged.update(changes)
        if (
            "estatus_atencion" not in changes
            and merged["requiere_respuesta"]
            and merged["estatus_atencion"] == "CONOCIMIENTO"
        ):
            merged["estatus_atencion"] = "PENDIENTE"
        if merged["fecha_oficio"] is None:
            merged["fecha_oficio"] = merged["fecha_recepcion"]
        # Un ATENDIDO importado sin fecha puede ajustar su plazo sin falsificar el cierre histórico.
        historical_attended = (
            merged["estatus_atencion"] == "ATENDIDO" and not merged["fecha_atencion"]
        )
        if historical_attended:
            merged["estatus_atencion"] = "PENDIENTE"
        try:
            validated = OficioCreate(**merged)
        except ValidationError as error:
            raise HTTPException(422, str(error)) from error
        for key in rule_fields | {"estatus_atencion"}:
            if key == "estatus_atencion" and historical_attended:
                continue
            changes[key] = getattr(validated, key)
    nullable = {
        "plazo_dias_habiles",
        "fecha_limite_respuesta",
        "nota_atencion",
        "oficio_respuesta_numero",
        "fecha_atencion",
    }
    if any(value is None and key not in nullable for key, value in changes.items()):
        raise HTTPException(422, "No puede vaciar un campo obligatorio.")
    status = changes.get("estatus_atencion", record.estatus_atencion)
    requires = changes.get("requiere_respuesta", record.requiere_respuesta)
    if status == "CONOCIMIENTO" and requires:
        raise HTTPException(422, "Conocimiento no puede requerir respuesta.")
    if (
        status == "ATENDIDO"
        and "estatus_atencion" in changes
        and not changes.get("fecha_atencion", record.fecha_atencion)
    ):
        raise HTTPException(422, "Debe indicar la fecha de atención.")
    return changes


def scoped_query(user):
    query = select(Oficio)
    if user.role == "Responsable_Area":
        query = query.where(Oficio.area_asignada == user.area)
    return query
