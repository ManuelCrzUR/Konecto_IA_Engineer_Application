"""Tests for app.domain.models (no DB, no LLM)."""

from __future__ import annotations

import json
import uuid
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.domain.models import (
    EXPECTED_ROWS,
    NUMERIC_FIELDS,
    Actuator,
    Catalog,
    ConversationRequest,
    ConversationResponse,
    Product,
    ToolTrace,
)

GOLDEN_PATH = Path(__file__).resolve().parent / "fixtures" / "golden_draft.json"
CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "actuators.json"


@pytest.fixture(scope="module")
def golden_dicts() -> list[dict[str, Any]]:
    if not GOLDEN_PATH.exists():
        pytest.skip("golden draft not available")
    rows: list[dict[str, Any]] = json.loads(GOLDEN_PATH.read_text())["rows"]
    return rows


@pytest.fixture(scope="module")
def golden(golden_dicts: list[dict[str, Any]]) -> list[Actuator]:
    return [Actuator.from_bench_row(r) for r in golden_dicts]


def test_golden_counts(golden: list[Actuator]) -> None:
    assert len(golden) == 68
    assert dict(Counter(a.table_id for a in golden)) == EXPECTED_ROWS


def test_rows_without_data(golden: list[Actuator]) -> None:
    empty = [a for a in golden if not a.has_data]
    assert len(empty) == 4
    assert all(a.table_id == "T3_wp_220v_3ph" for a in empty)
    assert sorted(a.part_number[:4] for a in empty) == ["761A", "761B", "762A", "762B"]


def test_non_csa_rows(golden: list[Actuator]) -> None:
    non_csa = [a for a in golden if not a.csa_certified]
    assert len(non_csa) == 5
    assert all(a.table_id == "T2_wp_220v_1ph" for a in non_csa)
    assert sorted(a.part_number[:4] for a in non_csa) == ["766A", "766B", "767A", "767B", "767C"]


def test_from_bench_row_rejects_unparsed(golden_dicts: list[dict[str, Any]]) -> None:
    bad = {**golden_dicts[0], "unparsed": {"fla_a": "1.?"}}
    with pytest.raises(ValueError):
        Actuator.from_bench_row(bad)


def test_extra_key_rejected(golden_dicts: list[dict[str, Any]]) -> None:
    d = {k: v for k, v in golden_dicts[0].items() if k != "unparsed"}
    with pytest.raises(ValidationError):
        Actuator.model_validate({**d, "bogus": 1})


def test_bad_part_number_rejected(golden_dicts: list[dict[str, Any]]) -> None:
    d = {k: v for k, v in golden_dicts[0].items() if k != "unparsed"}
    with pytest.raises(ValidationError):
        Actuator.model_validate({**d, "part_number": "13Z00000"})


def test_product_keeps_only_non_null(golden: list[Actuator]) -> None:
    for a in golden:
        p = Product.from_actuator(a, notes=["n"])
        assert p.notes == ["n"]
        assert p.has_data == a.has_data
        expected = {f: getattr(a, f) for f in NUMERIC_FIELDS if getattr(a, f) is not None}
        assert p.fields == expected
    na = next(a for a in golden if not a.has_data)
    assert Product.from_actuator(na).fields == {}


def test_request_validation() -> None:
    for q in ("", "   "):
        with pytest.raises(ValidationError):
            ConversationRequest(query=q)
    assert ConversationRequest(query="  hi ").query == "hi"
    with pytest.raises(ValidationError):
        ConversationRequest(query="x" * 2001)


def test_response_roundtrip(golden: list[Actuator]) -> None:
    resp = ConversationResponse(
        session_id=uuid.uuid4(),
        answer="ok",
        language="es",
        products=[Product.from_actuator(golden[0])],
        debug=[
            ToolTrace(
                tool="get_actuator", params={"part_number": "x"}, result={"a": [1]}, duration_ms=1.5
            )
        ],
    )
    again = ConversationResponse.model_validate_json(resp.model_dump_json())
    assert again == resp


def test_catalog_file_validates() -> None:
    if not CATALOG_PATH.exists():
        pytest.skip("actuators.json not generated yet")
    cat = Catalog.model_validate_json(CATALOG_PATH.read_text())
    assert len(cat.rows) == 68


def _row_764a() -> Product:
    catalog = Catalog.model_validate_json(CATALOG_PATH.read_text())
    row = next(r for r in catalog.rows if r.part_number == "764A00-11300000/A")
    return Product.from_actuator(row)


def test_product_json_writes_whole_floats_as_ints() -> None:
    data = json.loads(_row_764a().model_dump_json())
    assert data["fields"]["onoff_torque_nm"] == 750
    assert isinstance(data["fields"]["onoff_torque_nm"], int)
    assert data["fields"]["fla_60hz_a"] == 6.5
    assert isinstance(data["fields"]["fla_60hz_a"], float)


def test_product_python_dump_keeps_floats() -> None:
    value = _row_764a().model_dump()["fields"]["onoff_torque_nm"]
    assert value == 750.0
    assert isinstance(value, float)
    assert isinstance(_row_764a().model_dump(mode="json")["fields"]["onoff_torque_nm"], int)


def test_product_json_keeps_none_as_null() -> None:
    p = _row_764a().model_copy(update={"fields": {"fla_60hz_a": None, "lra_60hz_a": 12.0}})
    data = json.loads(p.model_dump_json())
    assert data["fields"] == {"fla_60hz_a": None, "lra_60hz_a": 12}


def test_product_json_roundtrips() -> None:
    p = _row_764a()
    assert Product.model_validate_json(p.model_dump_json()) == p
    assert Product.model_validate(json.loads(p.model_dump_json())) == p


def test_response_serializes_nested_product_fields_as_ints() -> None:
    resp = ConversationResponse(
        session_id=uuid.uuid4(), answer="ok", language="en", products=[_row_764a()]
    )
    data = json.loads(resp.model_dump_json())
    assert data["products"][0]["fields"]["onoff_torque_nm"] == 750
    assert isinstance(data["products"][0]["fields"]["onoff_torque_nm"], int)
