import argparse
import json
import sqlite3
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.db.session import make_engine, session_factory
from backend.app.main import bootstrap
from backend.app.services.excel_sync import import_excel


def main():
    parser = argparse.ArgumentParser(description="Mantenimiento local SICOA-SSG")
    parser.add_argument("command", choices=["sync", "backup", "import"])
    parser.add_argument("--source")
    parser.add_argument("--target")
    args = parser.parse_args()
    if args.command == "backup":
        if not args.source or not args.target:
            parser.error("backup requiere --source y --target")
        source, target = Path(args.source).resolve(), Path(args.target).resolve()
        if not source.is_file() or source == target:
            parser.error("El origen debe existir y ser distinto del destino")
        target.parent.mkdir(parents=True, exist_ok=True)
        with (
            sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as db,
            sqlite3.connect(target) as backup,
        ):
            db.backup(backup)
        print(json.dumps({"backup": str(target)}))
        return
    settings = Settings.from_env()
    engine = make_engine(settings)
    factory = session_factory(engine)
    changes = bootstrap(engine, factory, settings)
    if args.command == "import":
        if not args.source:
            parser.error("import requiere --source")
        with factory() as session:
            result = import_excel(
                session, Path(args.source).read_bytes(), source_name=Path(args.source).name
            )
            session.commit()
            print(json.dumps(result, ensure_ascii=True))
    else:
        print(json.dumps({"migrations": changes, "status": "ok"}))
    engine.dispose()


if __name__ == "__main__":
    main()
