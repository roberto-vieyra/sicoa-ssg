from sqlalchemy import func, select

from backend.app.core.security import hasher
from backend.app.db.models import Area, Counter, Funcionario, Oficio, User
from backend.app.services.directory import canonical_name, normalize

SEED_USERS = [
    ("admin", "SicoaSSG2026!", "Administrador", "SSG", "Subdirección de Servicios Generales"),
    ("oficialia", "Oficialia2026!", "Oficialia_Despachador", "SSG", "Mesa de Control SSG"),
    (
        "gai",
        "GerenciaGAI2026!",
        "Responsable_Area",
        "GAI",
        "Gerencia de Administración Inmobiliaria",
    ),
    ("gsa", "GerenciaGSA2026!", "Responsable_Area", "GSA", "Gerencia de Servicios Administrativos"),
    ("auditor", "Auditor2026!", "Auditor", "SSG", "Contraloría / Consulta"),
]
AREAS = [
    (
        "SSG",
        "Subdirección de Servicios Generales",
        "ARQ. MARTHA MARGARITA REYNÉS NOGUERA",
        ["MARIO", "RODRIGO", "PABLO ATENCIÓN CIUDADANA", "TADEO", "RUBI CHI", "TESSI"],
    ),
    ("GAI", "Gerencia de Administración Inmobiliaria", "", ["PATY GAI", "MANUEL CORREA"]),
    ("GSA", "Gerencia de Servicios Administrativos", "", ["ELI GSA"]),
    ("DRM", "Dirección de Recursos Materiales", "LCDA. ZAIRA MARIELA CARMONA RIVERA", ["RODRIGO"]),
    ("SA", "Subdirección de Adquisiciones", "LIC. LUIS MANUEL RUIZ JUÁREZ", ["ROCÍO"]),
]


def seed(session):
    for username, password, role, area, name in SEED_USERS:
        if not session.scalar(select(User.id).where(User.username == username)):
            session.add(
                User(
                    username=username,
                    password_hash=hasher.hash(password),
                    role=role,
                    area=area,
                    display_name=name,
                )
            )
    for key, name, holder, analysts in AREAS:
        if not session.scalar(select(Area.id).where(Area.clave == key)):
            session.add(
                Area(
                    clave=key, nombre=name, titular_nombre=holder, analistas_sugeridos_json=analysts
                )
            )
    for name, role, prefix in [
        (
            "ARQ. MARTHA MARGARITA REYNÉS NOGUERA",
            "SUBDIRECTORA DE SERVICIOS GENERALES",
            "UA/DRM/SSG/",
        ),
        ("LCDA. ZAIRA MARIELA CARMONA RIVERA", "DIRECTORA DE RECURSOS MATERIALES", "UA/DRM/"),
        ("TITULAR DE LA UNIDAD JURÍDICA", "TITULAR DE LA UNIDAD JURÍDICA", "UJ/"),
    ]:
        if not session.scalar(
            select(Funcionario.id).where(Funcionario.nombre_normalizado == normalize(name))
        ):
            session.add(
                Funcionario(
                    nombre_normalizado=normalize(name),
                    nombre_mostrar=canonical_name(name),
                    cargo=role,
                    prefijo_oficio_frecuente=prefix,
                )
            )
    if session.get(Counter, "folio") is None:
        maximum = max(
            (int(f[3:]) for f in session.scalars(select(Oficio.folio_ssg)) if f[3:].isdigit()),
            default=0,
        )
        session.add(Counter(key="folio", value=maximum))
    for year, maximum in session.execute(
        select(Oficio.anio, func.max(Oficio.consecutivo_anual)).group_by(Oficio.anio)
    ):
        if session.get(Counter, f"anio:{year}") is None:
            session.add(Counter(key=f"anio:{year}", value=maximum))
    session.flush()
