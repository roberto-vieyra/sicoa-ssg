from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import jwt
import pytest
from openpyxl import load_workbook
from reportlab.pdfgen.canvas import Canvas
from sqlalchemy import func, select

from backend.app.db.models import AuditLog, Oficio
from backend.app.services.pdf_generator import verify_single_page_letter_pdf
from backend.tests.conftest import token


def create(client, auth, payload):
    result = client.post("/api/oficios", headers=auth, json=payload)
    assert result.status_code == 201, result.text
    return result.json()


def tiny_pdf():
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792))
    canvas.drawString(50, 730, "Acuse de prueba")
    canvas.showPage()
    canvas.save()
    return stream.getvalue()


def test_authentication_and_jwt(client):
    assert client.get("/api/oficios").status_code == 401
    assert (
        client.post("/api/auth/login", json={"username": "admin", "password": "wrong"}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login", json={"username": "missing", "password": "wrong"}
        ).status_code
        == 401
    )
    auth = token(client)
    assert client.get("/api/auth/me", headers=auth).json()["role"] == "Administrador"
    secret = client.app.state.settings.jwt_secret
    for value in [jwt.encode({"sub": "admin", "exp": 1}, secret, algorithm="HS256"), "not-a-token"]:
        assert (
            client.get("/api/oficios", headers={"Authorization": f"Bearer {value}"}).status_code
            == 401
        )


@pytest.mark.parametrize(
    ("username", "password", "create_status"),
    [
        ("oficialia", "Oficialia2026!", 201),
        ("gai", "GerenciaGAI2026!", 403),
        ("gsa", "GerenciaGSA2026!", 403),
        ("auditor", "Auditor2026!", 403),
    ],
)
def test_roles(client, payload, username, password, create_status):
    assert (
        client.post(
            "/api/oficios", json=payload, headers=token(client, username, password)
        ).status_code
        == create_status
    )


def test_scope_and_read_only_auditor(client, auth, payload):
    record = create(client, auth, payload)
    path = f"/api/oficios/{record['id']}"
    gai = token(client, "gai", "GerenciaGAI2026!")
    gsa = token(client, "gsa", "GerenciaGSA2026!")
    auditor = token(client, "auditor", "Auditor2026!")
    assert client.get(path, headers=gsa).status_code == 403
    assert client.get("/api/oficios", headers=gsa).json()["total"] == 0
    assert client.get(path + "/historial", headers=gsa).status_code == 403
    assert client.get(path + "/volante-pdf", headers=gsa).status_code == 403
    assert (
        client.patch(path, json={"version": 1, "area_asignada": "GSA"}, headers=gai).status_code
        == 403
    )
    assert (
        client.patch(
            path, json={"version": 1, "estatus_atencion": "CANCELADO"}, headers=gai
        ).status_code
        == 403
    )
    assert (
        client.patch(path, json={"version": 1, "nota_atencion": "x"}, headers=auditor).status_code
        == 403
    )
    assert (
        client.post(
            path + "/atencion", data={"version": 1, "nota_atencion": "x"}, headers=auditor
        ).status_code
        == 403
    )
    assert (
        client.patch(
            path, json={"version": 1, "estatus_atencion": "EN_SEGUIMIENTO"}, headers=gai
        ).status_code
        == 200
    )
    assert client.get("/api/audit-logs", headers=auditor).status_code == 200


def test_optimistic_updates_audit_and_no_version_bypass(client, auth, payload):
    record = create(client, auth, payload)
    path = f"/api/oficios/{record['id']}"
    assert record["fecha_limite_respuesta"] == "2026-11-11"
    assert client.patch(path, json={"asunto": "changed"}, headers=auth).status_code == 422
    changed = client.put(path, json={"version": 1, "area_asignada": "GSA"}, headers=auth)
    assert changed.status_code == 200
    assert changed.json()["version"] == 2
    stale = client.patch(path, json={"version": 1, "asunto": "lost update"}, headers=auth)
    assert stale.status_code == 409
    assert stale.json()["detail"]["current"]["version"] == 2
    assert stale.json()["detail"]["current"]["asunto"] == payload["asunto"]
    history = client.get(path + "/historial", headers=auth).json()
    assert [item["action"] for item in history] == ["TURNO", "CREACION"]
    assert history[0]["before_json"]["area_asignada"] == "GAI"
    assert history[0]["after_json"]["area_asignada"] == "GSA"


def test_concurrent_writers_cannot_overwrite(client, auth, payload):
    record = create(client, auth, payload)

    def write(subject):
        return client.patch(
            f"/api/oficios/{record['id']}", headers=auth, json={"version": 1, "asunto": subject}
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(write, ["Cambio A", "Cambio B"])) == [200, 409]


def test_concurrent_creation_reserves_unique_folios(client, auth, payload):
    def write(index):
        return create(client, auth, {**payload, "numero_oficio": f"PRUEBA/{index}"})["folio_ssg"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        result = list(pool.map(write, range(8)))
    assert sorted(result) == [f"SSG{i:03d}" for i in range(1, 9)]


def test_directory_version_and_normalization(client, auth):
    response = client.post(
        "/api/funcionarios",
        headers=auth,
        json={"nombre_mostrar": "  JOSÉ   PÉREZ ", "cargo": "TITULAR"},
    )
    assert response.status_code == 201
    record = response.json()
    assert record["nombre_normalizado"] == "JOSE PEREZ"
    assert (
        client.post(
            "/api/funcionarios", headers=auth, json={"nombre_mostrar": "JOSE PEREZ"}
        ).status_code
        == 409
    )
    path = f"/api/funcionarios/{record['id']}"
    assert (
        client.patch(path, headers=auth, json={"version": 1, "cargo": "DIRECTOR"}).json()["version"]
        == 2
    )
    assert (
        client.put(path, headers=auth, json={"version": 1, "cargo": "OUTDATED"}).status_code == 409
    )
    assert client.patch(path, headers=auth, json={"cargo": "BYPASS"}).status_code == 422


def test_attention_atomic_upload_and_stale_cleanup(client, auth, payload):
    record = create(client, auth, payload)
    path = f"/api/oficios/{record['id']}"
    data = {
        "version": "1",
        "nota_atencion": "Mantenimiento realizado",
        "oficio_respuesta_numero": "UA/DRM/SSG/123",
        "fecha_atencion": "2026-11-10",
    }
    response = client.post(
        path + "/atencion",
        headers=auth,
        data=data,
        files={"file": ("../../acuse.pdf", tiny_pdf(), "application/pdf")},
    )
    assert response.status_code == 200, response.text
    result = response.json()
    assert result["version"] == 2 and result["estatus_atencion"] == "ATENDIDO"
    assert result["acuse_respuesta_nombre"] == "acuse.pdf"
    assert result["semaforo"]["codigo"] == "AZUL_ATENDIDO"
    assert "acuse_respuesta_ruta" not in result
    directory = client.app.state.settings.data_dir / "uploads"
    assert len(list(directory.glob("*.pdf"))) == 1
    assert (
        client.post(
            path + "/atencion",
            headers=auth,
            data=data,
            files={"file": ("stale.pdf", tiny_pdf(), "application/pdf")},
        ).status_code
        == 409
    )
    assert len(list(directory.glob("*.pdf"))) == 1
    pdf = client.get(path + "/documentos/acuse", headers=auth)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF-")
    assert client.get(path + "/historial", headers=auth).json()[0]["action"] == "CIERRE_CON_ACUSE"


def test_entry_upload_rejects_bad_file_and_missing_version(client, auth, payload):
    record = create(client, auth, payload)
    path = f"/api/oficios/{record['id']}/documento"
    assert (
        client.post(
            path, headers=auth, files={"file": ("x.pdf", b"not a pdf")}, data={"version": 1}
        ).status_code
        == 422
    )
    assert client.post(path, headers=auth, files={"file": ("x.pdf", tiny_pdf())}).status_code == 422
    assert client.post(
        path, headers=auth, files={"file": ("x.pdf", tiny_pdf())}, data={"version": 1}
    ).json()["documento_entrada_disponible"]


def test_export_and_pdf_endpoints(client, auth, payload):
    record = create(client, auth, {**payload, "asunto": '=HYPERLINK("evil")'})
    response = client.get("/api/oficios/export-excel", headers=auth)
    workbook = load_workbook(BytesIO(response.content))
    sheet = workbook["CORRESPONDENCIA 2026"]
    assert sheet.freeze_panes == "D3"
    assert sheet["L3"].data_type == "s"
    assert sheet["L3"].value == '=HYPERLINK("evil")'
    assert sheet["D3"].is_date
    workbook.close()
    for path, landscape in [
        (f"/api/oficios/{record['id']}/volante-pdf", False),
        ("/api/reportes/alertas-pdf", True),
        ("/api/reportes/acuse-entrega-pdf", True),
    ]:
        result = client.get(path, headers=auth)
        assert result.status_code == 200
        assert "attachment;" in result.headers["content-disposition"]
        verify_single_page_letter_pdf(result.content, landscape)


def test_cancelled_copies_and_invalid_payloads(client, auth, payload):
    copy = create(client, auth, {**payload, "naturaleza": "CC", "requiere_respuesta": False})
    assert copy["estatus_atencion"] == "CONOCIMIENTO"
    assert copy["fecha_limite_respuesta"] is None
    assert copy["semaforo"]["codigo"] == "GRIS_INFORMATIVO"
    assert (
        client.post(
            "/api/oficios", headers=auth, json={**payload, "plazo_tipo": "FECHA_FIJA"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/oficios", headers=auth, json={**payload, "area_asignada": "UNKNOWN"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/oficios/{copy['id']}", headers=auth, json={"version": 1, "asunto": None}
        ).status_code
        == 422
    )
    with client.app.state.sessions() as db:
        assert db.scalar(select(func.count()).select_from(Oficio)) == 1
        assert db.scalar(select(func.count()).select_from(AuditLog)) == 1


def test_reclassifying_copy_to_original_requires_attention(client, auth, payload):
    record = create(client, auth, {**payload, "naturaleza": "CC", "requiere_respuesta": False})
    result = client.patch(
        f"/api/oficios/{record['id']}",
        headers=auth,
        json={
            "version": 1,
            "naturaleza": "ORIGINAL",
            "requiere_respuesta": True,
            "plazo_tipo": "DIAS_HABILES_2",
        },
    )
    assert result.status_code == 200, result.text
    assert result.json()["estatus_atencion"] == "PENDIENTE"
    assert result.json()["fecha_limite_respuesta"] == "2026-11-10"
