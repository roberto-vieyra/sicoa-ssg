from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import ROOT, Settings


def make_engine(settings: Settings):
    url = make_url(settings.database_url)
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+pg8000")
    if url.get_backend_name() == "sqlite":
        if url.database and url.database != ":memory:":
            path = Path(url.database)
            path = path if path.is_absolute() else ROOT / path
            path.parent.mkdir(parents=True, exist_ok=True)
            url = url.set(database=str(path.resolve()))
        engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 30})

        @event.listens_for(engine, "connect")
        def sqlite_pragmas(connection, _):
            cursor = connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()
    else:
        engine = create_engine(url, pool_pre_ping=True)
    return engine


def session_factory(engine):
    return sessionmaker(engine, expire_on_commit=False)
