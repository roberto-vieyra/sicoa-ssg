import re
import unicodedata
from collections import Counter

from sqlalchemy import select

from backend.app.db.models import Funcionario
from backend.app.services.audit import log, snapshot


def normalize(value) -> str:
    text = " ".join(str(value or "").split()).upper()
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def canonical_name(value) -> str:
    name = " ".join(str(value or "").split()).upper()
    normalized = normalize(name)
    if "REYNES" in normalized and ("MARTHA" in normalized or normalized == "REYNES"):
        return "ARQ. MARTHA MARGARITA REYNÉS NOGUERA"
    if normalized in {"UNIDAD JURIDICA", "TITULAR DE LA UNIDAD JURIDICA"}:
        return "TITULAR DE LA UNIDAD JURÍDICA"
    return name


def infer_prefix(number: str) -> str:
    match = re.match(
        r"^([A-Za-zÁÉÍÓÚÑáéíóúñ]+(?:[/\-][A-Za-zÁÉÍÓÚÑáéíóúñ]+)*[/\-])", number.strip()
    )
    return match.group(1).upper() if match else ""


def populate_directory(session, records, actor):
    people = {item.nombre_normalizado: item for item in session.scalars(select(Funcionario))}
    existing = set(people)
    prefixes = {}
    for record in records:
        for role in ("dirigido", "firmante"):
            name = canonical_name(record.get(f"{role}_nombre", ""))
            if not name:
                continue
            key = normalize(name)
            if key not in people:
                person = Funcionario(
                    nombre_normalizado=key,
                    nombre_mostrar=name,
                    cargo=record.get(f"{role}_cargo", ""),
                    dependencia_unidad="",
                )
                people[key] = person
                session.add(person)
            if role == "firmante":
                prefix = infer_prefix(record.get("numero_oficio", ""))
                if prefix:
                    prefixes.setdefault(key, Counter())[prefix] += 1
        for copy in record.get("copias_dirigido_json", []):
            name = canonical_name(copy["nombre"])
            key = normalize(name)
            if key and key not in people:
                people[key] = Funcionario(
                    nombre_normalizado=key, nombre_mostrar=name, cargo=copy["cargo"]
                )
                session.add(people[key])
    changed = {}
    for key, counts in prefixes.items():
        person = people[key]
        if not person.prefijo_oficio_frecuente:
            if key in existing:
                changed[key] = snapshot(person)
            person.prefijo_oficio_frecuente = counts.most_common(1)[0][0]
    session.flush()
    for key in people.keys() - existing:
        log(session, actor, people[key], "CREACION")
    for key, before in changed.items():
        log(session, actor, people[key], "EDICION", before=before)
