"""DDL aditivo: no DROP, no reemplazo de tablas ni reinterpretación silenciosa de datos."""

from sqlalchemy import Index, UniqueConstraint, inspect
from sqlalchemy.schema import CreateColumn

from backend.app.db.models import Base


def migrate(engine) -> list[str]:
    changes = []
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.exec_driver_sql("SELECT pg_advisory_xact_lock(7340762026)")
        else:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        existing = set(inspect(conn).get_table_names())
        for table in Base.metadata.sorted_tables:
            if table.name not in existing:
                table.create(conn)
                changes.append(f"tabla:{table.name}")
                continue
            columns = {item["name"] for item in inspect(conn).get_columns(table.name)}
            quote = engine.dialect.identifier_preparer.quote
            for column in table.columns:
                if column.name in columns:
                    continue
                if column.primary_key or (not column.nullable and column.server_default is None):
                    raise RuntimeError(
                        f"Migración manual necesaria: {table.name}.{column.name} carece de un valor seguro."
                    )
                ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
                conn.exec_driver_sql(f"ALTER TABLE {quote(table.name)} ADD COLUMN {ddl}")
                changes.append(f"columna:{table.name}.{column.name}")
            indexes = {item["name"] for item in inspect(conn).get_indexes(table.name)}
            for index in table.indexes:
                if index.name not in indexes:
                    index.create(conn)
                    changes.append(f"indice:{index.name}")
            unique_columns = {
                tuple(item["column_names"])
                for item in inspect(conn).get_unique_constraints(table.name)
            }
            unique_columns.update(
                tuple(item["column_names"])
                for item in inspect(conn).get_indexes(table.name)
                if item.get("unique")
            )
            for constraint in table.constraints:
                if isinstance(constraint, UniqueConstraint):
                    names = tuple(column.name for column in constraint.columns)
                    if names not in unique_columns:
                        name = f"uq_{table.name}_{'_'.join(names)}"
                        # Adjuntar temporalmente el índice para generar DDL portable.
                        index = Index(name, *(table.c[n] for n in names), unique=True)
                        try:
                            index.create(conn)
                        finally:
                            table.indexes.discard(index)
                        changes.append(f"indice:{name}")
    return changes
