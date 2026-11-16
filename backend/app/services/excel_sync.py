import hashlib
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import PurePosixPath
from urllib.parse import unquote
from zipfile import BadZipFile, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.datetime import from_excel
from sqlalchemy import select, update

from backend.app.db.models import Counter, ImportBatch, Oficio
from backend.app.services.audit import log
from backend.app.services.calendar import PLAZOS, add_business_days, semaphore
from backend.app.services.directory import canonical_name, normalize, populate_directory

SHEET = "CORRESPONDENCIA 2026"
SHIFTED = {"SSG209", "SSG559", "SSG560", "SSG561", "SSG566", "SSG583"}
COLORS = {
    "ROJO_VENCIDO": "FCE8E6",
    "AMBAR_POR_VENCER": "FFF0CD",
    "VERDE_EN_TIEMPO": "DEF2E8",
    "AZUL_ATENDIDO": "DFEDFA",
    "GRIS_INFORMATIVO": "E7EBEF",
}
HEADERS = [
    "Año",
    "SSG",
    "No. De Oficio",
    "Fecha del oficio",
    "Fecha de Recepción",
    "Fecha Limite de Respuesta",
    "Semáforo de Vencimiento",
    "Dirigido",
    "Cargo",
    "Firmante",
    "Cargo",
    "Asunto",
    "Asignado a:",
    "Observaciones",
    "Documento",
    "Atención",
]


def text(value):
    return str(value).strip() if value is not None else ""


def parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, (int, float)) and 30000 < value < 80000:
        return from_excel(value).date()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(text(value), fmt).date()
        except ValueError:
            pass
    return None


def hyperlink(cell):
    if cell.hyperlink:
        return cell.hyperlink.target or cell.hyperlink.location or ""
    match = re.match(r'=HYPERLINK\("([^"]+)"', text(cell.value), re.I)
    return match.group(1) if match else ""


def file_name(link):
    return PurePosixPath(unquote(link).replace("\\", "/")).name if link else None


def assigned_area(value):
    normalized = normalize(value)
    present = [
        key for key in ("SSG", "GAI", "GSA", "DRM", "SA") if re.search(rf"\b{key}\b", normalized)
    ]
    # Los turnos compartidos permanecen en coordinación SSG; el detalle se conserva completo.
    return present[0] if len(present) == 1 else "SSG"


def parse_workbook(content: bytes):
    try:
        with ZipFile(BytesIO(content)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 100 * 1024 * 1024:
                raise ValueError("El libro descomprimido supera 100 MB.")
        workbook = load_workbook(BytesIO(content), data_only=False, keep_links=False)
    except (BadZipFile, KeyError, OSError) as error:
        raise ValueError("Archivo Excel inválido; se requiere .xlsx.") from error
    try:
        if SHEET not in workbook:
            raise ValueError(f"Falta la hoja {SHEET}.")
        sheet = workbook[SHEET]
        if sheet.max_row > 50000 or sheet.max_column > 100:
            raise ValueError("El libro excede los límites de importación.")
        headers = [normalize(cell.value) for cell in sheet[2][: len(HEADERS)]]
        # El original deja Año en blanco y añade una instrucción en el encabezado de Semáforo.
        if len(headers) == len(HEADERS):
            headers[0] = headers[0] or "ANO"
            headers[6] = headers[6].removesuffix("(NO EDITAR)").rstrip(" .")
        if headers != [normalize(label) for label in HEADERS]:
            raise ValueError("Encabezados incompatibles con la fila 2 de CORRESPONDENCIA 2026.")
        records, empty_folios, corrections, issues = [], [], [], []
        seen = set()
        for row_number, row in enumerate(sheet.iter_rows(min_row=3, max_col=16), 3):
            values = [cell.value for cell in row]
            folio, number = text(values[1]).upper(), text(values[2])
            if not number:
                if re.fullmatch(r"SSG\d{3,4}", folio):
                    empty_folios.append(folio)
                continue
            if not re.fullmatch(r"SSG\d{3,4}", folio) or int(folio[3:]) < 1:
                raise ValueError(f"Folio inválido en fila {row_number}: {folio}.")
            folio = f"SSG{int(folio[3:]):03d}"
            if folio in seen:
                raise ValueError(f"Folio duplicado en el libro: {folio}.")
            seen.add(folio)
            reception, issued, deadline = (
                parse_date(values[4]),
                parse_date(values[3]),
                parse_date(values[5]),
            )
            copies = []
            if values[5] and deadline is None and not text(values[5]).startswith("="):
                copies.append({"nombre": canonical_name(values[5]), "cargo": text(values[6])})
                corrections.append(folio)
            observation = text(values[13])
            attention, document = text(values[15]), text(values[14])
            notes = normalize(attention + " " + document)
            is_copy = bool(re.search(r"(?:^|\W)C\.?\s*C\.?(?:$|\W)", normalize(observation)))
            state = "CONOCIMIENTO" if is_copy else "PENDIENTE"
            if "CANCELADO" in normalize(attention + " " + observation):
                state = "CANCELADO"
            elif (
                "RESPONDIDO" in normalize(attention)
                or normalize(attention) == "DOC"
                or hyperlink(row[15])
            ):
                state = "ATENDIDO"
            days, term = None, "FECHA_FIJA" if deadline else "SIN_PLAZO"
            day_match = re.search(r"\b(\d{1,3})\s*DIAS?\s+HABILES?\b", notes)
            if re.search(r"\b24\s*(?:HR|HRS|HORAS?)\b", notes):
                days, term = 1, "HORAS_24"
            elif day_match:
                days = int(day_match.group(1))
                if not 1 <= days <= 365:
                    raise ValueError(f"Plazo inválido en {folio}.")
                term = next((key for key, value in PLAZOS.items() if value == days), "FECHA_FIJA")
            if days and reception and not deadline:
                deadline = add_business_days(reception, days)
            if deadline and values[5] and parse_date(values[5]):
                term = "FECHA_FIJA"  # La fecha explícita tiene prioridad sobre notas.
            requires = not is_copy or bool(days or deadline)
            if requires and state == "CONOCIMIENTO":
                state = "PENDIENTE"
            if not reception or not issued:
                issues.append(
                    {
                        "folio": folio,
                        "detalle": "Fecha histórica ausente; se conserva sin inventarla.",
                    }
                )
            entry_link, answer_link = hyperlink(row[14]), hyperlink(row[15])
            record = {
                "anio": 2026,
                "folio_ssg": folio,
                "consecutivo_anual": int(folio[3:]),
                "numero_oficio": number,
                "fecha_oficio": issued,
                "fecha_recepcion": reception,
                "naturaleza": "CC" if is_copy else "ORIGINAL",
                "requiere_respuesta": requires,
                "plazo_tipo": term,
                "plazo_dias_habiles": days,
                "fecha_limite_respuesta": deadline,
                "dirigido_nombre": canonical_name(values[7]),
                "dirigido_cargo": text(values[8]),
                "copias_dirigido_json": copies,
                "firmante_nombre": canonical_name(values[9]),
                "firmante_cargo": text(values[10]),
                "asunto": text(values[11]),
                "area_asignada": assigned_area(values[12]),
                "responsables_detalle": text(values[12]),
                "observaciones_fisicas": observation,
                "tiene_documento_entrada": bool(entry_link or normalize(document) == "DOC"),
                "documento_entrada_nombre": file_name(entry_link),
                "documento_entrada_ruta": f"legacy:{entry_link}" if entry_link else None,
                "estatus_atencion": state,
                "nota_atencion": attention or None,
                "oficio_respuesta_numero": file_name(answer_link),
                "fecha_atencion": None,
                "tiene_acuse_respuesta": bool(answer_link),
                "acuse_respuesta_nombre": file_name(answer_link),
                "acuse_respuesta_ruta": f"legacy:{answer_link}" if answer_link else None,
            }
            records.append(record)
        return records, {
            "filas_validas": len(records),
            "folios_vacios": empty_folios,
            "correcciones": corrections,
            "incidencias": issues,
        }
    finally:
        workbook.close()


def import_excel(session, content: bytes, actor="sistema", source_name="Base.xlsx"):
    digest = hashlib.sha256(content).hexdigest()
    previous = session.scalar(select(ImportBatch).where(ImportBatch.sha256 == digest))
    if previous:
        return {**previous.summary, "importados": 0, "ya_importado": True}
    records, summary = parse_workbook(content)
    existing = set(session.scalars(select(Oficio.folio_ssg)))
    imported, duplicates = 0, []
    new_records = []
    for record in records:
        if record["folio_ssg"] in existing:
            duplicates.append(record["folio_ssg"])
            continue
        item = Oficio(**record)
        session.add(item)
        session.flush()
        log(session, actor, item, "IMPORTACION")
        new_records.append(record)
        imported += 1
    populate_directory(session, new_records, actor)
    maximum = max((int(item["folio_ssg"][3:]) for item in records), default=0)
    for key in ("folio", "anio:2026"):
        if session.get(Counter, key) is None:
            session.add(Counter(key=key, value=maximum))
        else:
            session.execute(
                update(Counter)
                .where(Counter.key == key, Counter.value < maximum)
                .values(value=maximum)
            )
    summary.update(
        {
            "importados": imported,
            "duplicados_conservados": duplicates,
            "sha256": digest,
            "ya_importado": False,
        }
    )
    batch = ImportBatch(sha256=digest, source_name=source_name, summary=summary)
    session.add(batch)
    session.flush()
    log(session, actor, batch, "IMPORTACION", after=summary)
    return summary


def export_excel(records, reference: date) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = SHEET
    sheet.append([f"SICOA-SSG | Correspondencia | Corte: {reference.isoformat()}"])
    sheet.append(HEADERS)
    sheet.freeze_panes = "D3"
    sheet.sheet_view.showGridLines = False
    for row_number, item in enumerate(records, 3):
        status = semaphore(item, reference)
        sheet.append(
            [
                item.anio,
                item.folio_ssg,
                item.numero_oficio,
                item.fecha_oficio,
                item.fecha_recepcion,
                item.fecha_limite_respuesta,
                status["etiqueta"],
                item.dirigido_nombre,
                item.dirigido_cargo,
                item.firmante_nombre,
                item.firmante_cargo,
                item.asunto,
                item.responsables_detalle or item.area_asignada,
                item.observaciones_fisicas,
                item.documento_entrada_nombre or ("DOC" if item.tiene_documento_entrada else ""),
                "CANCELADO"
                if item.estatus_atencion == "CANCELADO"
                else ("RESPONDIDO" if item.estatus_atencion == "ATENDIDO" else item.nota_atencion),
            ]
        )
        for column_number in range(1, len(HEADERS) + 1):
            cell = sheet.cell(row_number, column_number)
            # Exportar texto literal; nunca ejecutar fórmulas provenientes de expedientes.
            if isinstance(cell.value, str):
                cell.data_type = "s"
            cell.font = Font(name="Arial", size=10, color="24313E")
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            if cell.column in {4, 5, 6}:
                cell.number_format = "dd/mm/yyyy"
        sheet.cell(row_number, 7).fill = PatternFill("solid", fgColor=COLORS[status["codigo"]])
        sheet.row_dimensions[row_number].height = 60
    for cell in sheet[2]:
        cell.fill = PatternFill("solid", fgColor="26333E")
        cell.font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    sheet.row_dimensions[2].height = 32
    sheet["A1"].font = Font(name="Arial", size=14, bold=True, color="691C32")
    widths = [9, 13, 34, 16, 16, 18, 24, 38, 38, 38, 38, 85, 25, 32, 42, 42]
    for index, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    sheet.auto_filter.ref = f"A2:P{sheet.max_row}"
    sheet.print_title_rows = "1:2"
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_LETTER
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    stream = BytesIO()
    workbook.save(stream)
    workbook.close()
    return stream.getvalue()
