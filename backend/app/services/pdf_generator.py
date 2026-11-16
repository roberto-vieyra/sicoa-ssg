from datetime import date
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph

from backend.app.services.calendar import semaphore

INK = colors.HexColor("#26333e")
WINE = colors.HexColor("#691c32")
GOLD = colors.HexColor("#9f7a3e")
PALE = colors.HexColor("#f2f4f6")
STATUS = {
    "ROJO_VENCIDO": "#a52c30",
    "AMBAR_POR_VENCER": "#855700",
    "VERDE_EN_TIEMPO": "#15694d",
    "AZUL_ATENDIDO": "#205a91",
    "GRIS_INFORMATIVO": "#56636e",
}
LOGO = Path(__file__).resolve().parents[1] / "assets" / "sello-ssg.png"


def verify_single_page_letter_pdf(pdf_bytes: bytes, landscape=False) -> dict:
    reader = PdfReader(BytesIO(pdf_bytes), strict=True)
    if len(reader.pages) != 1:
        raise ValueError("El documento debe contener exactamente una página.")
    page = reader.pages[0]
    expected = (792, 612) if landscape else (612, 792)
    for box in (page.mediabox, page.cropbox):
        if tuple(float(v) for v in box) != (0.0, 0.0, *map(float, expected)):
            raise ValueError(f"Tamaño Carta incorrecto; se esperaba {expected} pt.")
    if page.rotation != 0:
        raise ValueError("El documento no debe depender de una rotación de página.")
    return {"pages": 1, "width": expected[0], "height": expected[1]}


def clean(value):
    return (
        str(value or "Sin registro")
        .replace("\u2011", "-")
        .replace("\u2013", "-")
        .replace("\u2014", "-")
    )


def text_box(canvas, value, x, y, width, height, size=9, bold=False, color=INK):
    original = clean(value)
    value = original
    font = "Helvetica-Bold" if bold else "Helvetica"
    while True:
        style = ParagraphStyle(
            "cell",
            fontName=font,
            fontSize=size,
            leading=size * 1.28,
            textColor=color,
            alignment=TA_LEFT,
            splitLongWords=True,
        )
        para = Paragraph(escape(value).replace("\n", "<br/>"), style)
        _, used_height = para.wrap(width, height)
        if used_height <= height:
            para.drawOn(canvas, x, y + height - used_height)
            return value != original
        if size > 7.5:
            size -= 0.5
        else:
            low, high = 0, len(original)
            while low < high:
                middle = (low + high + 1) // 2
                candidate = original[:middle].rstrip() + " [...]"
                test = Paragraph(escape(candidate).replace("\n", "<br/>"), style)
                if test.wrap(width, height)[1] <= height:
                    low = middle
                else:
                    high = middle - 1
            value = original[:low].rstrip() + " [...]"
            para = Paragraph(escape(value).replace("\n", "<br/>"), style)
            _, used_height = para.wrap(width, height)
            para.drawOn(canvas, x, y + height - used_height)
            return True


def header(canvas, width, height, title, reference):
    canvas.setTitle(title)
    canvas.setAuthor("SICOA-SSG / Subdirección de Servicios Generales")
    if LOGO.exists():
        canvas.drawImage(str(LOGO), 32, height - 78, width=48, height=48, mask="auto")
    canvas.setFillColor(WINE)
    canvas.setFont("Helvetica-Bold", 11)
    canvas.drawString(92, height - 39, "SUBDIRECCIÓN DE SERVICIOS GENERALES")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK)
    canvas.drawString(92, height - 54, "SICOA-SSG  /  CONTROL DE OFICIOS, TURNOS Y ALERTAS")
    canvas.setStrokeColor(GOLD)
    canvas.line(32, height - 88, width - 32, height - 88)
    text_box(canvas, title, 32, height - 126, width - 64, 28, 12, True)
    canvas.setFont("Courier", 8)
    canvas.drawRightString(width - 32, 25, f"CORTE {reference.isoformat()}   |   1 / 1")


def field(canvas, label, value, x, y, width, height):
    canvas.setFillColor(PALE)
    canvas.roundRect(x, y, width, height, 3, fill=1, stroke=0)
    text_box(canvas, label.upper(), x + 9, y + height - 22, width - 18, 13, 7.5, True, WINE)
    return text_box(canvas, value, x + 9, y + 8, width - 18, height - 31, 9)


def finish(canvas, stream, landscape=False):
    canvas.showPage()
    canvas.save()
    content = stream.getvalue()
    verify_single_page_letter_pdf(content, landscape)
    return content


def volante_pdf(item, reference: date) -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(612, 792), pageCompression=1)
    header(canvas, 612, 792, "VOLANTE OFICIAL DE TURNO Y CONTROL DE OFICIO", reference)
    status = semaphore(item, reference)
    canvas.setFont("Courier-Bold", 22)
    canvas.setFillColor(WINE)
    canvas.drawString(32, 641, item.folio_ssg)
    text_box(
        canvas,
        status["etiqueta"],
        250,
        636,
        330,
        28,
        12,
        True,
        colors.HexColor(STATUS[status["codigo"]]),
    )
    clipped = False
    clipped |= field(canvas, "Número de oficio", item.numero_oficio, 32, 565, 548, 60)
    clipped |= field(
        canvas,
        "Firmante / origen",
        f"{item.firmante_nombre}\n{item.firmante_cargo}",
        32,
        477,
        268,
        80,
    )
    clipped |= field(
        canvas, "Dirigido a", f"{item.dirigido_nombre}\n{item.dirigido_cargo}", 312, 477, 268, 80
    )
    copies = (
        "; ".join(f"{p['nombre']} - {p['cargo']}" for p in item.copias_dirigido_json)
        or "Sin co-destinatarios"
    )
    clipped |= field(canvas, "Copias / co-destinatarios", copies, 32, 420, 548, 49)
    field(canvas, "Recepción", item.fecha_recepcion, 32, 357, 173, 55)
    field(
        canvas,
        "Plazo fatal",
        item.fecha_limite_respuesta or "SIN PLAZO DEFINIDO",
        217,
        357,
        173,
        55,
    )
    field(canvas, "Naturaleza", item.naturaleza, 402, 357, 178, 55)
    clipped |= field(canvas, "Asunto", item.asunto, 32, 215, 548, 134)
    clipped |= field(
        canvas,
        "Instrucciones de turno",
        f"ÁREA: {item.area_asignada} | RESPONSABLE: {item.responsables_detalle or 'Por asignar'}\n{item.observaciones_fisicas}",
        32,
        135,
        548,
        72,
    )
    canvas.setStrokeColor(colors.HexColor("#9ca6af"))
    canvas.roundRect(32, 50, 548, 77, 3, fill=0, stroke=1)
    text_box(canvas, "ACUSE DE RECEPCIÓN FÍSICA", 43, 100, 525, 16, 8, True)
    text_box(
        canvas,
        "Nombre y firma: __________________________   Fecha y hora: __________________\n\nSello de recepción:",
        43,
        61,
        525,
        35,
        8,
    )
    if clipped:
        text_box(
            canvas,
            "[...] Texto abreviado. Consulte el expediente completo en SICOA-SSG.",
            32,
            29,
            390,
            13,
            7.5,
        )
    return finish(canvas, stream)


def kpis(records):
    result = []
    for area in ("SSG", "GAI", "GSA", "DRM", "SA"):
        subset = [
            r
            for r in records
            if r.area_asignada == area
            and r.requiere_respuesta
            and r.estatus_atencion != "CANCELADO"
        ]
        attended = sum(r.estatus_atencion == "ATENDIDO" for r in subset)
        result.append(
            {
                "area": area,
                "total": len(subset),
                "atendidos": attended,
                "cumplimiento": round(100 * attended / len(subset), 1) if subset else 0,
            }
        )
    return result


def alertas_pdf(records, reference: date) -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(792, 612), pageCompression=1)
    header(canvas, 792, 612, "REPORTE EJECUTIVO DE SEMÁFORO Y ALERTAS", reference)
    for index, metric in enumerate(kpis(records)):
        x = 32 + index * 148
        field(
            canvas,
            metric["area"],
            f"{metric['atendidos']} / {metric['total']} atendidos\nCumplimiento: {metric['cumplimiento']}%",
            x,
            411,
            136,
            64,
        )
    pending = [
        r
        for r in records
        if r.requiere_respuesta and r.estatus_atencion not in {"ATENDIDO", "CANCELADO"}
    ]
    rank = {"ROJO_VENCIDO": 0, "AMBAR_POR_VENCER": 1, "VERDE_EN_TIEMPO": 2}
    pending.sort(
        key=lambda r: (
            rank.get(semaphore(r, reference)["codigo"], 3),
            r.fecha_limite_respuesta or date.min,
            r.folio_ssg,
        )
    )
    limit = 12
    visible = pending[:limit]
    columns = [
        (32, 68, "FOLIO"),
        (100, 54, "ÁREA"),
        (154, 92, "PLAZO"),
        (246, 106, "SEMÁFORO"),
        (352, 64, "D. HÁB."),
        (416, 344, "ASUNTO"),
    ]
    table_header(canvas, columns, 381)
    row_height = min(28, 300 / max(len(visible), 1))
    for index, item in enumerate(visible):
        y = 381 - (index + 1) * row_height
        state = semaphore(item, reference)
        if index % 2 == 0:
            canvas.setFillColor(PALE)
            canvas.rect(32, y, 728, row_height, fill=1, stroke=0)
        values = [
            item.folio_ssg,
            item.area_asignada,
            item.fecha_limite_respuesta or "Sin plazo",
            state["etiqueta"],
            state["dias_habiles"] if state["dias_habiles"] is not None else "-",
            item.asunto,
        ]
        for (x, width, _), value in zip(columns, values, strict=True):
            text_box(
                canvas,
                str(value),
                x + 5,
                y + 3,
                width - 10,
                row_height - 5,
                8,
                color=colors.HexColor(STATUS[state["codigo"]]) if x == 246 else INK,
            )
    if not visible:
        text_box(canvas, "Sin oficios pendientes de respuesta.", 40, 330, 650, 30, 11)
    omitted = len(pending) - len(visible)
    text_box(
        canvas,
        f"Se muestran {len(visible)} de {len(pending)} pendientes, por prioridad. Omitidos: {omitted}; detalle completo en Excel.\nD. háb.: días restantes; negativos = atraso. Cumplimiento = atendidos / requieren respuesta, excluye cancelados.",
        32,
        43,
        728,
        33,
        7.5,
    )
    return finish(canvas, stream, True)


def table_header(canvas, columns, y):
    canvas.setFillColor(INK)
    canvas.rect(32, y, 728, 23, fill=1, stroke=0)
    for x, width, title in columns:
        text_box(canvas, title, x + 5, y + 4, width - 10, 15, 7.5, True, colors.white)


def acuse_entrega_pdf(records, reference: date) -> bytes:
    stream = BytesIO()
    canvas = Canvas(stream, pagesize=(792, 612), pageCompression=1)
    header(canvas, 792, 612, "MINUTA / HOJA DE RUTA DE ENTREGA FÍSICA", reference)
    selected = records[:10]
    text_box(
        canvas,
        f"Fecha de entrega: __________________    Entrega: __________________    Lote: {len(selected)} oficios",
        32,
        446,
        728,
        29,
        9,
    )
    columns = [
        (32, 68, "FOLIO"),
        (100, 194, "NÚMERO DE OFICIO"),
        (294, 68, "ÁREA"),
        (362, 168, "RESPONSABLE"),
        (530, 230, "NOMBRE, FIRMA, FECHA Y HORA"),
    ]
    table_header(canvas, columns, 415)
    for index, item in enumerate(selected):
        y = 415 - (index + 1) * 33
        canvas.setStrokeColor(colors.HexColor("#c5ccd2"))
        canvas.line(32, y, 760, y)
        values = [
            item.folio_ssg,
            item.numero_oficio,
            item.area_asignada,
            item.responsables_detalle,
            "",
        ]
        for (x, width, _), value in zip(columns, values, strict=True):
            if value:
                text_box(canvas, value, x + 5, y + 4, width - 10, 25, 8)
    if not selected:
        text_box(canvas, "No hay oficios en el lote seleccionado.", 40, 360, 650, 30, 11)
    text_box(
        canvas,
        f"Se incluyen {len(selected)} de {len(records)} oficios. Restantes: {max(0, len(records) - 10)}. Genere el siguiente lote con los folios correspondientes.\nObservaciones de entrega: __________________________________________________________________________________",
        32,
        40,
        728,
        35,
        8,
    )
    return finish(canvas, stream, True)
