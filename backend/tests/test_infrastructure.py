import ssl
from datetime import date
from io import BytesIO
from unittest.mock import patch

import pytest
from pypdf import PdfReader, PdfWriter
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateTable

from backend.app.core.config import Settings
from backend.app.core.http_client import TIMEOUT, async_http_client, http_client
from backend.app.db.migrations import migrate
from backend.app.db.models import Base, Oficio
from backend.app.db.session import make_engine, session_factory
from backend.app.services.pdf_generator import (
    acuse_entrega_pdf,
    alertas_pdf,
    verify_single_page_letter_pdf,
    volante_pdf,
)


def test_http_client_enforces_corporate_tls_defaults():
    for factory, name in [(http_client, "Client"), (async_http_client, "AsyncClient")]:
        with patch(f"backend.app.core.http_client.httpx.{name}") as client:
            factory()
            kwargs = client.call_args.kwargs
            assert isinstance(kwargs["verify"], ssl.SSLContext)
            assert kwargs["verify"].verify_mode == ssl.CERT_REQUIRED
            assert kwargs["verify"].check_hostname
            assert kwargs["trust_env"] is True
            assert kwargs["http2"] is False
            assert kwargs["timeout"] == TIMEOUT
    assert (TIMEOUT.connect, TIMEOUT.read, TIMEOUT.write, TIMEOUT.pool) == (3, 6, 6, 3)


def test_migration_is_additive_idempotent_and_boolean_defaults_are_portable(tmp_path):
    settings = Settings(database_url=f"sqlite:///{tmp_path / 'legacy.db'}", data_dir=tmp_path)
    engine = make_engine(settings)
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE oficios (id INTEGER PRIMARY KEY, folio_ssg VARCHAR(20), numero_oficio VARCHAR(250))"
        )
        conn.exec_driver_sql("INSERT INTO oficios VALUES (1, 'SSG001', 'HISTORICO/1')")
    assert migrate(engine)
    assert migrate(engine) == []
    with session_factory(engine)() as db:
        record = db.get(Oficio, 1)
        assert record.numero_oficio == "HISTORICO/1"
        assert record.version == 1
        assert record.requiere_respuesta is True
        assert record.tiene_documento_entrada is False
        assert record.tiene_acuse_respuesta is False
        assert record.copias_dirigido_json == []
    with engine.connect() as conn:
        assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    assert "ix_oficios_folio_ssg" in {
        item["name"] for item in inspect(engine).get_indexes("oficios")
    }
    engine.dispose()


def test_models_compile_for_both_database_dialects():
    for dialect in [sqlite.dialect(), postgresql.dialect()]:
        for table in Base.metadata.sorted_tables:
            statement = str(CreateTable(table).compile(dialect=dialect))
            assert table.name in statement
            assert "JSONB" not in statement


def test_migrator_refuses_unsafe_missing_required_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unsafe.db'}")
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        conn.exec_driver_sql("INSERT INTO users VALUES (1)")
    with pytest.raises(RuntimeError, match="Migración manual"):
        migrate(engine)
    with engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT id FROM users").scalar() == 1
    engine.dispose()


def test_extreme_pdf_content_and_preflight_reject_wrong_geometry(real_client):
    with real_client.app.state.sessions() as db:
        records = list(db.scalars(select(Oficio)))
        item = records[0]
        item.asunto = "CONTENIDO MUY EXTENSO ÁÉÍÓÚ Ñ " * 1200
        item.responsables_detalle = "RESPONSABLE EXTENSO " * 40
        item.copias_dirigido_json = [
            {"nombre": "DESTINATARIO MUY EXTENSO " * 20, "cargo": "CARGO " * 50}
        ] * 20
        volante = volante_pdf(item, date(2026, 11, 10))
        verify_single_page_letter_pdf(volante)
        assert "Texto abreviado" in PdfReader(BytesIO(volante)).pages[0].extract_text()
        for content in [
            alertas_pdf(records, date(2026, 11, 10)),
            acuse_entrega_pdf(records, date(2026, 11, 10)),
        ]:
            verify_single_page_letter_pdf(content, True)
        wrong = PdfWriter()
        wrong.add_blank_page(595, 842)
        stream = BytesIO()
        wrong.write(stream)
        with pytest.raises(ValueError, match="Tamaño Carta"):
            verify_single_page_letter_pdf(stream.getvalue())
        wrong.add_blank_page(612, 792)
        stream = BytesIO()
        wrong.write(stream)
        with pytest.raises(ValueError, match="exactamente una página"):
            verify_single_page_letter_pdf(stream.getvalue())
