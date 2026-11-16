from datetime import date, datetime

from sqlalchemy import inspect

from backend.app.db.models import AuditLog


def snapshot(entity) -> dict:
    result = {}
    for column in inspect(entity).mapper.column_attrs:
        value = getattr(entity, column.key)
        result[column.key] = value.isoformat() if isinstance(value, (date, datetime)) else value
    return result


def log(session, actor, entity, action, before=None, after=None):
    session.add(
        AuditLog(
            actor_username=actor,
            entity_type=entity.__tablename__,
            entity_id=str(entity.id),
            action=action,
            before_json=before,
            after_json=after if after is not None else snapshot(entity),
        )
    )
