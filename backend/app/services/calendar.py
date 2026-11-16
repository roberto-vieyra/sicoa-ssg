from datetime import date, timedelta

PLAZOS = {
    "HORAS_24": 1,
    "DIAS_HABILES_2": 2,
    "DIAS_HABILES_3": 3,
    "DIAS_HABILES_5": 5,
    "DIAS_HABILES_10": 10,
}


def add_business_days(start: date, days: int) -> date:
    if days < 0:
        raise ValueError("Los días de plazo no pueden ser negativos.")
    current = start
    while days:
        current += timedelta(days=1)
        if current.weekday() < 5:
            days -= 1
    return current


def business_days_between(start: date, end: date) -> int:
    if end < start:
        return -business_days_between(end, start)
    days = 0
    while start < end:
        start += timedelta(days=1)
        days += start.weekday() < 5
    return days


def semaphore(record, reference: date) -> dict:
    def result(code, label, days=None):
        return {"codigo": code, "etiqueta": label, "dias_habiles": days}

    get = record.get if isinstance(record, dict) else lambda key: getattr(record, key)
    state = get("estatus_atencion")
    if state == "CANCELADO":
        return result("GRIS_INFORMATIVO", "CANCELADO")
    if state == "ATENDIDO":
        return result("AZUL_ATENDIDO", "ATENDIDO")
    if not get("requiere_respuesta"):
        return result(
            "GRIS_INFORMATIVO", "INFORMATIVO / CC" if get("naturaleza") == "CC" else "INFORMATIVO"
        )
    deadline = get("fecha_limite_respuesta")
    if isinstance(deadline, str):
        deadline = date.fromisoformat(deadline)
    if not deadline:
        return result("AMBAR_POR_VENCER", "PENDIENTE DE PLAZO")
    days = business_days_between(reference, deadline)
    if deadline < reference:
        return result("ROJO_VENCIDO", "VENCIDO", days)
    if days <= 2:
        return result("AMBAR_POR_VENCER", "POR VENCER", days)
    return result("VERDE_EN_TIEMPO", "EN TIEMPO", days)
