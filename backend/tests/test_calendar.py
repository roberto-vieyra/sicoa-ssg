from datetime import date

import pytest

from backend.app.services.calendar import add_business_days, business_days_between, semaphore


@pytest.mark.parametrize(
    ("start", "count", "expected"),
    [
        ("2026-11-06", 1, "2026-11-09"),
        ("2026-11-06", 3, "2026-11-11"),
        ("2026-12-31", 2, "2027-01-04"),
        ("2026-11-07", 0, "2026-11-07"),
        ("2026-11-08", 5, "2026-11-13"),
        ("2026-11-06", 7, "2026-11-17"),
    ],
)
def test_business_days(start, count, expected):
    assert add_business_days(date.fromisoformat(start), count).isoformat() == expected


@pytest.mark.parametrize(
    ("state", "requires", "deadline", "code", "days"),
    [
        ("CANCELADO", True, "2026-11-02", "GRIS_INFORMATIVO", None),
        ("ATENDIDO", True, "2026-11-02", "AZUL_ATENDIDO", None),
        ("CONOCIMIENTO", False, None, "GRIS_INFORMATIVO", None),
        ("PENDIENTE", True, None, "AMBAR_POR_VENCER", None),
        ("PENDIENTE", True, "2026-11-09", "ROJO_VENCIDO", -1),
        ("PENDIENTE", True, "2026-11-10", "AMBAR_POR_VENCER", 0),
        ("EN_SEGUIMIENTO", True, "2026-11-12", "AMBAR_POR_VENCER", 2),
        ("PENDIENTE", True, "2026-11-13", "VERDE_EN_TIEMPO", 3),
    ],
)
def test_semaphore(state, requires, deadline, code, days):
    result = semaphore(
        {
            "estatus_atencion": state,
            "requiere_respuesta": requires,
            "naturaleza": "CC" if not requires else "ORIGINAL",
            "fecha_limite_respuesta": deadline,
        },
        date(2026, 11, 10),
    )
    assert result["codigo"] == code
    assert result["dias_habiles"] == days


def test_weekend_is_overdue_even_when_no_business_day_elapsed():
    result = semaphore(
        {
            "estatus_atencion": "PENDIENTE",
            "requiere_respuesta": True,
            "naturaleza": "ORIGINAL",
            "fecha_limite_respuesta": "2026-11-06",
        },
        date(2026, 11, 7),
    )
    assert result["codigo"] == "ROJO_VENCIDO"
    assert result["dias_habiles"] == 0
    assert business_days_between(date(2026, 11, 6), date(2026, 11, 9)) == 1
    with pytest.raises(ValueError):
        add_business_days(date(2026, 11, 6), -1)
