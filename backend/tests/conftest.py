import os
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url

from backend.app.core.config import ROOT, Settings
from backend.app.main import create_app


@contextmanager
def test_database(tmp_path):
    """Cuando TEST_DATABASE_URL está presente, cada fixture crea una base PostgreSQL aislada."""
    postgres_url = os.environ.get("TEST_DATABASE_URL")
    if not postgres_url:
        yield f"sqlite:///{tmp_path / 'test.db'}"
        return
    url = make_url(postgres_url)
    assert url.get_backend_name() == "postgresql", (
        "TEST_DATABASE_URL debe apuntar a PostgreSQL de pruebas."
    )
    database = "sicoa_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database}"')
    try:
        yield url.set(database=database).render_as_string(hide_password=False)
    finally:
        # Se elimina exclusivamente la base aleatoria creada por esta fixture.
        with admin.connect() as connection:
            connection.exec_driver_sql(f'DROP DATABASE "{database}"')
        admin.dispose()


@pytest.fixture(scope="session")
def real_excel():
    path = Path(os.environ.get("BASE_XLSX_PATH", str(ROOT / "data/Base.xlsx")))
    assert path.is_file(), f"Se requiere el Base.xlsx real para esta validación: {path}"
    return path.read_bytes()


@pytest.fixture
def client(tmp_path):
    with test_database(tmp_path) as url:
        settings = Settings(
            database_url=url,
            data_dir=tmp_path,
            jwt_secret="tests-only-secret-with-more-than-32-chars",
            auto_import=False,
        )
        app = create_app(settings)
        with TestClient(app) as http:
            yield http


@pytest.fixture(scope="module")
def real_client(tmp_path_factory, real_excel):
    tmp_path = tmp_path_factory.mktemp("real-data")
    (tmp_path / "Base.xlsx").write_bytes(real_excel)
    with test_database(tmp_path) as url:
        settings = Settings(
            database_url=url,
            data_dir=tmp_path,
            jwt_secret="real-import-test-secret-more-than-32-chars",
        )
        with TestClient(create_app(settings)) as http:
            yield http


def token(client, username="admin", password="SicoaSSG2026!"):
    response = client.post("/api/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def auth(client):
    return token(client)


@pytest.fixture
def payload():
    return {
        "numero_oficio": "UA/DRM/001/2026",
        "fecha_oficio": "2026-11-06",
        "fecha_recepcion": "2026-11-06",
        "asunto": "Solicitud de mantenimiento preventivo",
        "area_asignada": "GAI",
        "plazo_tipo": "DIAS_HABILES_3",
    }
