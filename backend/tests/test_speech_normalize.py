import pytest

from app.speech.normalize import normalize_transcript as n

CASES = [
    ("764A00-113000000, barra A", "764A00-113000000, barra A"),
    ("763 B0011330 C00 barra oblicua a.", "763B00-11330C00/A."),
    ("766 A00 11320,000/A", "766A00-11320000/A"),
    ("764 by 30-11,320,000 slash A", "764X30-11320000/A"),
    ("765 A00 11,320,000 slash A", "765A00-11320000/A"),
    ("761 A0011330 C00 barra A", "761A00-11330C00/A"),
    ("762 por 30", "762X30"),
    ("762x30", "762X30"),
    ("764/30-11,320,000/A", "764/30-11,320,000/A"),
    ("761-0011-330-C00-A", "761-0011-330-C00-A"),
    ("Busco un actuador de 24 voltios con al menos 100 Nm.", None),
    ("Dame el LRA 50 Hz", None),
    ("1,330 in-lbs", None),
    ("220V", None),
    ("dos actuadores por 30 euros", None),
    ("Compare 764X30-11320000/A and 765A00-11320000/A", None),
    (
        "Compare 764 A00 11300000 barra A y 765 a00 11320000 slash a",
        "Compare 764A00-11300000/A y 765A00-11320000/A",
    ),
    ("¿Qué es 764 by 30-11,320,000 slash A?", "¿Qué es 764X30-11320000/A?"),
    ("dame 764a00 guion 11300000 barra a, por favor", "dame 764A00-11300000/A, por favor"),
    ("764A00 raya 11300000 slash A", "764A00-11300000/A"),
    ("764A00 dash 11300000 slash A", "764A00-11300000/A"),
    ("  datos de 764A00  ", "datos de 764A00"),
    ("  hola  ", "hola"),
    ("764X30-11320000/A, 2 actuators", "764X30-11320000/A, 2 actuators"),
    ("", ""),
    ("¿Qué velocidad tiene el 764 a 60 Hz?", None),
    ("el 762 a 50 hertz", None),
    ("¿Hay un 761 a 24 V?", None),
    ("761 x 20 Nm", None),
    ("y el 762 por 30?", "y el 762X30?"),
    ("764 a 00 a 60 Hz", "764A00 a 60 Hz"),
    ("76 4a 00", "764A00"),
    ("764 a 00", "764A00"),
]


@pytest.mark.parametrize(("raw", "want"), CASES)
def test_normalize(raw: str, want: str | None) -> None:
    assert n(raw) == (raw.strip() if want is None else want)


def test_idempotent() -> None:
    for raw, _ in CASES:
        assert n(n(raw)) == n(raw)
