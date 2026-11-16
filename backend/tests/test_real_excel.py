from datetime import date
from io import BytesIO

import pytest
from openpyxl import Workbook, load_workbook
from sqlalchemy import func, select

from backend.app.db.models import AuditLog, Funcionario, Oficio
from backend.app.services.calendar import semaphore
from backend.app.services.excel_sync import HEADERS, SHEET, SHIFTED, parse_workbook
from backend.tests.conftest import token


def test_reordered_import_headers_are_rejected():
    workbook = Workbook()
    workbook.active.title = SHEET
    workbook.active.append(["Correspondencia"])
    headers = HEADERS.copy()
    headers[7], headers[9] = headers[9], headers[7]
    workbook.active.append(headers)
    content = BytesIO()
    workbook.save(content)
    workbook.close()
    with pytest.raises(ValueError, match="Encabezados incompatibles"):
        parse_workbook(content.getvalue())


def test_real_962_rows_six_displacements_and_blank_folios(real_excel):
    records, summary = parse_workbook(real_excel)
    assert len(records) == summary["filas_validas"] == 962
    assert set(summary["correcciones"]) == SHIFTED
    assert summary["folios_vacios"] == ["SSG963", "SSG964", "SSG965", "SSG966"]
    indexed = {row["folio_ssg"]: row for row in records}
    source = load_workbook(BytesIO(real_excel), data_only=False)
    for row in source.active.iter_rows(min_row=3):
        folio = str(row[1].value)
        if folio in SHIFTED:
            fixed = indexed[folio]
            assert fixed["copias_dirigido_json"][0]["nombre"] == str(row[5].value).strip()
            assert fixed["copias_dirigido_json"][0]["cargo"] == str(row[6].value).strip()
            assert fixed["fecha_limite_respuesta"] is None
    source.close()
    assert indexed["SSG816"]["oficio_respuesta_numero"] == "UA-DRM-SSG-GSA-14-10-02-2026.pdf"
    assert indexed["SSG331"]["estatus_atencion"] == "CANCELADO"
    assert indexed["SSG514"]["estatus_atencion"] == "ATENDIDO"
    assert indexed["SSG001"]["dirigido_nombre"] == "ARQ. MARTHA MARGARITA REYNÉS NOGUERA"
    assert indexed["SSG598"]["plazo_tipo"] == "HORAS_24"
    assert indexed["SSG722"]["plazo_dias_habiles"] == 3
    assert indexed["SSG818"]["plazo_dias_habiles"] == 10
    seven = [r for r in records if r["plazo_dias_habiles"] == 7]
    assert len(seven) == 1 and seven[0]["plazo_tipo"] == "FECHA_FIJA"
    assert semaphore(indexed["SSG331"], date(2026, 11, 10))["codigo"] == "GRIS_INFORMATIVO"
    assert semaphore(indexed["SSG816"], date(2026, 11, 10))["codigo"] == "AZUL_ATENDIDO"
    assert semaphore(indexed["SSG598"], date(2026, 11, 10))["codigo"] == "ROJO_VENCIDO"
    assert semaphore(indexed["SSG962"], date(2026, 11, 10))["etiqueta"] == "PENDIENTE DE PLAZO"


def test_real_import_endpoint_idempotence_directory_and_next_folio(real_client, real_excel):
    auth = token(real_client)
    assert real_client.get("/api/oficios", headers=auth).json()["total"] == 962
    assert real_client.get("/api/oficios/next-folio", headers=auth).json()["folio_ssg"] == "SSG963"
    result = real_client.post(
        "/api/oficios/import-excel", headers=auth, files={"file": ("Base.xlsx", real_excel)}
    )
    assert result.status_code == 200
    assert result.json()["ya_importado"] is True
    assert result.json()["importados"] == 0
    with real_client.app.state.sessions() as session:
        assert session.scalar(select(func.count()).select_from(Oficio)) == 962
        people = session.scalars(select(Funcionario)).all()
        assert len(people) > 30
        assert len({person.nombre_normalizado for person in people}) == len(people)
        assert any(person.prefijo_oficio_frecuente == "UF/DC/" for person in people)
        logged = session.scalars(
            select(AuditLog).where(
                AuditLog.entity_type == "funcionarios_directorio", AuditLog.action == "CREACION"
            )
        ).all()
        assert any(entry.after_json["prefijo_oficio_frecuente"] == "UF/DC/" for entry in logged)


def test_real_export_and_all_pdf_geometries(real_client, tmp_path):
    from backend.app.services.pdf_generator import verify_single_page_letter_pdf

    auth = token(real_client)
    response = real_client.get("/api/oficios/export-excel", headers=auth)
    workbook = load_workbook(BytesIO(response.content))
    assert workbook.active.max_row == 964
    assert workbook.active["B964"].value == "SSG962"
    assert workbook.active["G3"].fill.fgColor.rgb[-6:] != "000000"
    workbook.close()
    for path, landscape in [
        ("/api/oficios/962/volante-pdf", False),
        ("/api/reportes/alertas-pdf", True),
        ("/api/reportes/acuse-entrega-pdf", True),
    ]:
        result = real_client.get(path, headers=auth)
        assert result.status_code == 200
        verify_single_page_letter_pdf(result.content, landscape)
        (tmp_path / (path.rsplit("/", 1)[-1] + ".pdf")).write_bytes(result.content)
