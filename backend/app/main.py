from contextlib import asynccontextmanager
from datetime import date
from io import BytesIO
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pypdf import PdfReader
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError

from backend.app.core.config import ROOT, Settings
from backend.app.core.security import (
    DUMMY_HASH,
    check_scope,
    current_user,
    get_db,
    issue_token,
    require_dispatcher,
    require_writer,
    verify_password,
)
from backend.app.db.migrations import migrate
from backend.app.db.models import Area, AuditLog, Counter, Funcionario, ImportBatch, Oficio, User
from backend.app.db.seed import seed
from backend.app.db.session import make_engine, session_factory
from backend.app.schemas import FuncionarioInput, FuncionarioPatch, Login, OficioCreate, OficioPatch
from backend.app.services.audit import log
from backend.app.services.calendar import semaphore
from backend.app.services.directory import canonical_name, normalize
from backend.app.services.excel_sync import export_excel, import_excel
from backend.app.services.operations import (
    create_oficio,
    mutate,
    scoped_query,
    serialize,
    validate_patch,
)
from backend.app.services.pdf_generator import acuse_entrega_pdf, alertas_pdf, kpis, volante_pdf


def bootstrap(engine, sessions, settings):
    changes = migrate(engine)
    with sessions() as db:
        db.execute(
            text(
                "SELECT pg_advisory_xact_lock(7340762027)"
                if engine.dialect.name == "postgresql"
                else "BEGIN IMMEDIATE"
            )
        )
        seed(db)
        if settings.auto_import and not db.scalar(select(func.count()).select_from(Oficio)):
            source = next(
                (p for p in [settings.data_dir / "Base.xlsx", ROOT / "Base.xlsx"] if p.exists()),
                None,
            )
            if source:
                import_excel(db, source.read_bytes())
        db.commit()
    return changes


def create_app(settings: Settings | None = None):
    config = settings or Settings.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)
    engine = make_engine(config)
    sessions = session_factory(engine)

    @asynccontextmanager
    async def lifespan(_):
        bootstrap(engine, sessions, config)
        yield
        engine.dispose()

    app = FastAPI(
        title="SICOA-SSG", version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None
    )
    app.state.settings, app.state.engine, app.state.sessions = config, engine, sessions
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH"],
        allow_headers=["Authorization", "Content-Type"],
        expose_headers=["Content-Disposition"],
    )

    @app.exception_handler(IntegrityError)
    async def integrity_error(_, __):
        return JSONResponse(
            status_code=409,
            content={
                "detail": "El registro ya existe o cambió durante la operación. Recargue antes de intentar otra vez."
            },
        )

    @app.exception_handler(ValueError)
    async def value_error(_, error):
        return JSONResponse(status_code=422, content={"detail": str(error)})

    @app.get("/api/health")
    def health(db=Depends(get_db)):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": engine.dialect.name}

    @app.post("/api/auth/login")
    def login(body: Login, db=Depends(get_db)):
        user = db.scalar(select(User).where(User.username == body.username))
        valid = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
        if not valid or not user or not user.active:
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        return {
            "access_token": issue_token(user, config),
            "token_type": "bearer",
            "user": user_data(user),
        }

    @app.get("/api/auth/me")
    def me(user=Depends(current_user)):
        return user_data(user)

    @app.get("/api/config")
    def configuration(user=Depends(current_user), db=Depends(get_db)):
        return {
            "today": config.today(),
            "timezone": config.timezone,
            "business_calendar": "lunes a viernes; sin días inhábiles adicionales",
            "areas": [serialize(a, config.today()) for a in db.scalars(select(Area))],
        }

    @app.get("/api/funcionarios")
    def directory(q: str = "", user=Depends(current_user), db=Depends(get_db)):
        query = select(Funcionario).where(Funcionario.activo.is_(True))
        if q:
            query = query.where(
                Funcionario.nombre_normalizado.contains(normalize(q), autoescape=True)
            )
        return [
            serialize(p, config.today())
            for p in db.scalars(query.order_by(Funcionario.nombre_normalizado))
        ]

    @app.post("/api/funcionarios", status_code=201)
    def add_person(body: FuncionarioInput, user=Depends(current_user), db=Depends(get_db)):
        require_dispatcher(user)
        values = body.model_dump()
        values["nombre_mostrar"] = canonical_name(values["nombre_mostrar"])
        person = Funcionario(**values, nombre_normalizado=normalize(values["nombre_mostrar"]))
        db.add(person)
        db.flush()
        log(db, user.username, person, "CREACION")
        db.commit()
        return serialize(person, config.today())

    @app.patch("/api/funcionarios/{person_id}")
    @app.put("/api/funcionarios/{person_id}")
    def update_person(
        person_id: int, body: FuncionarioPatch, user=Depends(current_user), db=Depends(get_db)
    ):
        require_dispatcher(user)
        person = db.get(Funcionario, person_id)
        if not person:
            raise HTTPException(404, "Funcionario no encontrado.")
        changes = body.model_dump(exclude_unset=True, exclude={"version"})
        if not changes or any(value is None for value in changes.values()):
            raise HTTPException(422, "Se requieren cambios con valores válidos.")
        if "nombre_mostrar" in changes:
            changes["nombre_mostrar"] = canonical_name(changes["nombre_mostrar"])
            changes["nombre_normalizado"] = normalize(changes["nombre_mostrar"])
        mutate(db, person, body.version, changes, user.username, "EDICION", config.today())
        db.commit()
        return serialize(person, config.today())

    @app.get("/api/oficios/next-folio")
    def next_folio(user=Depends(current_user), db=Depends(get_db)):
        number = db.get(Counter, "folio").value + 1
        return {"folio_ssg": f"SSG{number:03d}", "disponible": number <= 9999, "preview": True}

    @app.get("/api/oficios")
    def list_oficios(
        q: str = "",
        area: str = "",
        estado: str = "",
        semaforo: str = "",
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=200),
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        query = scoped_query(user)
        if q:
            query = query.where(
                or_(
                    Oficio.folio_ssg.ilike(f"%{q}%"),
                    Oficio.numero_oficio.ilike(f"%{q}%"),
                    Oficio.asunto.ilike(f"%{q}%"),
                    Oficio.firmante_nombre.ilike(f"%{q}%"),
                )
            )
        if area:
            query = query.where(Oficio.area_asignada == area)
        if estado:
            query = query.where(Oficio.estatus_atencion == estado)
        reference = config.today()
        start = (page - 1) * page_size
        ordered = query.order_by(Oficio.id.desc())
        if semaforo:
            matched = [
                r for r in db.scalars(ordered) if semaphore(r, reference)["codigo"] == semaforo
            ]
            total = len(matched)
            records = matched[start : start + page_size]
        else:
            total = db.scalar(select(func.count()).select_from(query.subquery()))
            records = db.scalars(ordered.offset(start).limit(page_size))
        return {
            "items": [serialize(r, reference) for r in records],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    @app.get("/api/reportes/resumen")
    def summary(user=Depends(current_user), db=Depends(get_db)):
        items = list(db.scalars(scoped_query(user)))
        reference = config.today()
        statuses = [semaphore(r, reference)["codigo"] for r in items]
        return {
            "total": len(items),
            "vencidos": statuses.count("ROJO_VENCIDO"),
            "por_vencer": statuses.count("AMBAR_POR_VENCER"),
            "en_tiempo": statuses.count("VERDE_EN_TIEMPO"),
            "atendidos": statuses.count("AZUL_ATENDIDO"),
            "informativos": statuses.count("GRIS_INFORMATIVO"),
            "gerencias": kpis(items),
            "fecha_referencia": reference,
        }

    @app.post("/api/oficios/import-excel")
    async def upload_excel(
        file: UploadFile = File(...), user=Depends(current_user), db=Depends(get_db)
    ):
        require_dispatcher(user)
        content = await bounded_upload(file, config.max_upload_bytes)
        result = import_excel(
            db, content, user.username, safe_filename(file.filename or "Base.xlsx")
        )
        db.commit()
        return result

    @app.get("/api/oficios/importaciones")
    def imports(user=Depends(current_user), db=Depends(get_db)):
        require_dispatcher(user)
        return [
            serialize(batch, config.today())
            for batch in db.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(20))
        ]

    @app.get("/api/oficios/export-excel")
    def excel(user=Depends(current_user), db=Depends(get_db)):
        content = export_excel(
            db.scalars(scoped_query(user).order_by(Oficio.id)).all(), config.today()
        )
        return download(
            content,
            "correspondencia-2026.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    @app.post("/api/oficios", status_code=201)
    def create(body: OficioCreate, user=Depends(current_user), db=Depends(get_db)):
        require_dispatcher(user)
        record = create_oficio(db, body, user.username)
        db.commit()
        return serialize(record, config.today())

    def get_record(db, record_id, user):
        record = db.get(Oficio, record_id)
        if not record:
            raise HTTPException(404, "Oficio no encontrado.")
        check_scope(user, record)
        return record

    @app.get("/api/oficios/{record_id}")
    def read(record_id: int, user=Depends(current_user), db=Depends(get_db)):
        return serialize(get_record(db, record_id, user), config.today())

    @app.patch("/api/oficios/{record_id}")
    @app.put("/api/oficios/{record_id}")
    def edit(record_id: int, body: OficioPatch, user=Depends(current_user), db=Depends(get_db)):
        record = get_record(db, record_id, user)
        require_writer(user, record)
        changes = body.model_dump(exclude_unset=True, exclude={"version"})
        allowed = {"estatus_atencion", "nota_atencion", "oficio_respuesta_numero", "fecha_atencion"}
        if user.role == "Responsable_Area" and (
            not set(changes) <= allowed
            or changes.get("estatus_atencion") in {"CANCELADO", "CONOCIMIENTO"}
        ):
            raise HTTPException(
                403, "Un responsable solo puede registrar seguimiento o atención de su área."
            )
        if not changes:
            raise HTTPException(422, "No hay cambios para guardar.")
        changes = validate_patch(record, changes)
        action = (
            "CIERRE"
            if changes.get("estatus_atencion") == "ATENDIDO"
            else "TURNO"
            if {"area_asignada", "responsables_detalle"}.intersection(changes)
            else "EDICION"
        )
        mutate(db, record, body.version, changes, user.username, action, config.today())
        db.commit()
        return serialize(record, config.today())

    async def save_pdf(file):
        content = await bounded_upload(file, config.max_upload_bytes)
        if not content.startswith(b"%PDF-"):
            raise HTTPException(422, "Se requiere un archivo PDF válido.")
        try:
            parsed = PdfReader(BytesIO(content), strict=True)
            if parsed.is_encrypted or not parsed.pages:
                raise ValueError("PDF cifrado o vacío.")
        except Exception as error:
            raise HTTPException(422, "El PDF no se puede leer o está cifrado.") from error
        relative = f"uploads/{uuid4().hex}.pdf"
        destination = config.data_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return relative, destination

    @app.post("/api/oficios/{record_id}/documento")
    async def entry_document(
        record_id: int,
        version: int = Form(..., ge=1),
        file: UploadFile = File(...),
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        record = get_record(db, record_id, user)
        require_dispatcher(user)
        relative, destination = await save_pdf(file)
        try:
            mutate(
                db,
                record,
                version,
                {
                    "tiene_documento_entrada": True,
                    "documento_entrada_nombre": safe_filename(file.filename or "entrada.pdf"),
                    "documento_entrada_ruta": relative,
                },
                user.username,
                "CARGA_DOCUMENTO",
                config.today(),
            )
            db.commit()
        except Exception:
            db.rollback()
            destination.unlink(missing_ok=True)
            raise
        return serialize(record, config.today())

    @app.post("/api/oficios/{record_id}/atencion")
    async def attention(
        record_id: int,
        version: int = Form(..., ge=1),
        nota_atencion: str = Form(..., min_length=1, max_length=20000),
        oficio_respuesta_numero: str = Form("", max_length=500),
        fecha_atencion: date | None = Form(None),
        file: UploadFile | None = File(None),
        user=Depends(current_user),
        db=Depends(get_db),
    ):
        record = get_record(db, record_id, user)
        require_writer(user, record)
        changes = {
            "estatus_atencion": "ATENDIDO",
            "nota_atencion": nota_atencion,
            "oficio_respuesta_numero": oficio_respuesta_numero,
            "fecha_atencion": fecha_atencion or config.today(),
        }
        destination = None
        if file:
            relative, destination = await save_pdf(file)
            changes.update(
                {
                    "tiene_acuse_respuesta": True,
                    "acuse_respuesta_nombre": safe_filename(file.filename or "acuse.pdf"),
                    "acuse_respuesta_ruta": relative,
                }
            )
        try:
            mutate(
                db,
                record,
                version,
                changes,
                user.username,
                "CIERRE_CON_ACUSE" if file else "CIERRE",
                config.today(),
            )
            db.commit()
        except Exception:
            db.rollback()
            if destination:
                destination.unlink(missing_ok=True)
            raise
        return serialize(record, config.today())

    @app.get("/api/oficios/{record_id}/documentos/{kind}")
    def document(record_id: int, kind: str, user=Depends(current_user), db=Depends(get_db)):
        record = get_record(db, record_id, user)
        if kind not in {"entrada", "acuse"}:
            raise HTTPException(404, "Tipo de documento no encontrado.")
        relative = (
            record.documento_entrada_ruta if kind == "entrada" else record.acuse_respuesta_ruta
        )
        name = (
            record.documento_entrada_nombre if kind == "entrada" else record.acuse_respuesta_nombre
        )
        if not relative or not relative.startswith("uploads/"):
            raise HTTPException(
                404, "Referencia histórica: el archivo todavía no se ha cargado a este equipo."
            )
        destination = (config.data_dir / relative).resolve()
        if (
            not destination.is_relative_to((config.data_dir / "uploads").resolve())
            or not destination.is_file()
        ):
            raise HTTPException(404, "Documento no disponible.")
        return FileResponse(
            destination, media_type="application/pdf", filename=name or "documento.pdf"
        )

    @app.get("/api/oficios/{record_id}/volante-pdf")
    def volante(record_id: int, user=Depends(current_user), db=Depends(get_db)):
        record = get_record(db, record_id, user)
        return download(volante_pdf(record, config.today()), f"volante-{record.folio_ssg}.pdf")

    @app.get("/api/reportes/alertas-pdf")
    def alerts(user=Depends(current_user), db=Depends(get_db)):
        return download(
            alertas_pdf(list(db.scalars(scoped_query(user))), config.today()), "alertas-ssg.pdf"
        )

    @app.get("/api/reportes/acuse-entrega-pdf")
    def delivery(
        ids: str = "", offset: int = Query(0, ge=0), user=Depends(current_user), db=Depends(get_db)
    ):
        query = scoped_query(user).order_by(Oficio.id)
        if ids:
            try:
                selected = [int(value) for value in ids.split(",")]
            except ValueError as error:
                raise HTTPException(
                    422, "Los identificadores deben ser enteros separados por comas."
                ) from error
            query = query.where(Oficio.id.in_(selected))
        else:
            query = query.where(Oficio.estatus_atencion.not_in(["ATENDIDO", "CANCELADO"]))
        items = list(db.scalars(query))[offset:]
        return download(acuse_entrega_pdf(items, config.today()), "acuse-entrega-ssg.pdf")

    @app.get("/api/oficios/{record_id}/historial")
    def history(record_id: int, user=Depends(current_user), db=Depends(get_db)):
        get_record(db, record_id, user)
        return [
            serialize(item, config.today())
            for item in db.scalars(
                select(AuditLog)
                .where(AuditLog.entity_type == "oficios", AuditLog.entity_id == str(record_id))
                .order_by(AuditLog.id.desc())
            )
        ]

    @app.get("/api/audit-logs")
    def audit_logs(
        limit: int = Query(100, ge=1, le=500), user=Depends(current_user), db=Depends(get_db)
    ):
        if user.role not in {"Administrador", "Auditor"}:
            raise HTTPException(403, "La bitácora general requiere Administrador o Auditor.")
        return [
            serialize(item, config.today())
            for item in db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit))
        ]

    frontend_dist = ROOT / "frontend/dist"
    if (frontend_dist / "index.html").is_file():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="consola")
    return app


def user_data(user):
    return {key: getattr(user, key) for key in ("username", "role", "area", "display_name")}


async def bounded_upload(file, maximum):
    data = bytearray()
    while chunk := await file.read(1024 * 1024):
        data.extend(chunk)
        if len(data) > maximum:
            raise HTTPException(413, "El archivo supera el límite de 20 MB.")
    return bytes(data)


def safe_filename(value):
    return value.replace("\\", "/").split("/")[-1][:250]


def download(content, filename, media_type="application/pdf"):
    return Response(
        content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
