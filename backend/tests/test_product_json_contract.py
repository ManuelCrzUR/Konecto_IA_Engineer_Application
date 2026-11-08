"""Black-box tests for the Product JSON contract (see Product docstring).

Whole-number floats in `fields` are written as ints in JSON; python-mode dumps
keep floats; the stored Actuator format is unchanged.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest

from app.domain.models import NUMERIC_FIELDS, Actuator, ConversationResponse, Product

CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "actuators.json"
FLOAT_WHOLE = re.compile(r'"\w+": ?-?\d+\.0[,}\]]')


def _rows() -> list[Actuator]:
    raw = json.loads(CATALOG_PATH.read_text())["rows"]
    return [Actuator.model_validate(r) for r in raw]


ROWS = _rows()


def _product(fields: dict[str, float | None]) -> Product:
    return Product(
        part_number="X",
        enclosure="weatherproof",
        voltage="110V",
        phase=1,
        service="on_off",
        has_data=True,
        fields=fields,
    )


def _check_spelling(got: dict, expected: dict) -> None:
    assert got.keys() == expected.keys()
    for k, v in expected.items():
        g = got[k]
        assert g == v
        if float(v).is_integer():
            assert type(g) is int, (k, g)
        else:
            assert type(g) is float, (k, g)


def test_catalog_has_68_rows() -> None:
    assert len(ROWS) == 68


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r.table_id}-{r.part_number}")
def test_real_row_json_fields(row: Actuator) -> None:
    p = Product.from_actuator(row)
    expected = {f: getattr(row, f) for f in NUMERIC_FIELDS if getattr(row, f) is not None}
    _check_spelling(p.model_dump(mode="json")["fields"], expected)
    # raw text never has "N.0" for fields
    assert not FLOAT_WHOLE.search(p.model_dump_json())
    parsed = json.loads(p.model_dump_json())["fields"]
    _check_spelling(parsed, expected)


@pytest.mark.parametrize("row", ROWS, ids=lambda r: f"{r.table_id}-{r.part_number}")
def test_real_row_python_mode_keeps_floats(row: Actuator) -> None:
    fields = Product.from_actuator(row).model_dump()["fields"]
    assert all(type(v) is float for v in fields.values())


def test_none_preserved() -> None:
    p = _product({"a": None, "b": 2.0})
    d = p.model_dump(mode="json")["fields"]
    assert d == {"a": None, "b": 2}
    assert d["a"] is None and type(d["b"]) is int
    assert '"a":null' in p.model_dump_json().replace(" ", "")
    assert p.model_dump()["fields"]["a"] is None


def test_edge_values() -> None:
    p = _product({"z": 0.0, "big": 79700.0, "frac": 1.25, "neg": -3.0, "small": 0.5})
    d = p.model_dump(mode="json")["fields"]
    assert d == {"z": 0, "big": 79700, "frac": 1.25, "neg": -3, "small": 0.5}
    assert type(d["z"]) is int and type(d["big"]) is int and type(d["neg"]) is int
    assert type(d["frac"]) is float and type(d["small"]) is float
    text = p.model_dump_json()
    assert '"big":79700,' in text.replace(" ", "")
    assert not FLOAT_WHOLE.search(text)


def test_empty_fields() -> None:
    p = _product({})
    assert p.model_dump(mode="json")["fields"] == {}
    assert p.model_dump_json()


@pytest.mark.parametrize("row", ROWS[:: max(1, len(ROWS) // 10)], ids=lambda r: r.part_number)
def test_round_trip_json(row: Actuator) -> None:
    p = Product.from_actuator(row, notes=["n"])
    back = Product.model_validate_json(p.model_dump_json())
    assert back == p
    assert all(type(v) is float for v in back.fields.values())
    assert Product.model_validate(p.model_dump(mode="json")) == p


def test_nested_conversation_response() -> None:
    row = next(r for r in ROWS if r.has_data)
    p = Product.from_actuator(row)
    resp = ConversationResponse(session_id=uuid.uuid4(), answer="x", language="en", products=[p])
    expected = {f: getattr(row, f) for f in NUMERIC_FIELDS if getattr(row, f) is not None}
    _check_spelling(resp.model_dump(mode="json")["products"][0]["fields"], expected)
    text = resp.model_dump_json()
    assert not FLOAT_WHOLE.search(text)
    _check_spelling(json.loads(text)["products"][0]["fields"], expected)
    again = ConversationResponse.model_validate_json(text)
    assert again.products[0] == p


def test_actuator_serialization_unchanged() -> None:
    a = next(r for r in ROWS if r.part_number == "764A00-11300000/A")
    d = a.model_dump(mode="json")
    assert d["onoff_torque_nm"] == 750.0
    assert type(d["onoff_torque_nm"]) is float
    assert re.search(r'"onoff_torque_nm":\s*750\.0', a.model_dump_json())
    assert type(a.model_dump()["onoff_torque_nm"]) is float


def test_actuator_all_rows_floats_in_json() -> None:
    for r in ROWS:
        d = r.model_dump(mode="json")
        for f in NUMERIC_FIELDS:
            if getattr(r, f) is not None:
                assert type(d[f]) is float


def test_other_fields_unchanged() -> None:
    row = next(r for r in ROWS if r.phase == 3 and r.has_data)
    p = Product.from_actuator(row)
    d = p.model_dump(mode="json")
    assert d["phase"] == 3 and type(d["phase"]) is int
    assert d["csa_certified"] is True and d["has_data"] is True
    assert d["part_number"] == row.part_number
    na = next(r for r in ROWS if not r.has_data)
    dn = Product.from_actuator(na).model_dump(mode="json")
    assert dn["has_data"] is False and dn["fields"] == {}
    star = next((r for r in ROWS if not r.csa_certified), None)
    if star is not None:
        assert Product.from_actuator(star).model_dump(mode="json")["csa_certified"] is False
    assert _product({}).model_dump(mode="json")["phase"] == 1
    p2 = Product(part_number="X", enclosure="e", voltage="24V", service="s", has_data=False)
    assert p2.model_dump(mode="json")["phase"] is None
