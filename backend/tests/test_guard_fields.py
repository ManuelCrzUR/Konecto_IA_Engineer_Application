"""D-51: a figure followed by a unit must come from that product's field with that unit."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.agent import response as R
from app.domain.models import Actuator, ToolTrace

ROWS = json.loads((Path(__file__).parents[1] / "data/processed/actuators.json").read_text())["rows"]
BY_PN = {r["part_number"]: r for r in ROWS}
A764 = Actuator.model_validate(BY_PN["764A00-11300000/A"]).model_dump(mode="json")
A765 = Actuator.model_validate(BY_PN["765B00-11300000/A"]).model_dump(mode="json")
TOL = "Allowable motor voltage tolerance: +/- 10%"
P764 = "764A00-11300000/A"  # 750 Nm, 6650 in-lbs, FLA 6.5 A, LRA 7.3 A, 180 W, 25 %, 30 s, 12 c/h
P765 = "765B00-11300000/A"  # 108 s, FLA 7 A, 3000 Nm


def found(a: dict[str, Any]) -> ToolTrace:
    res = {"status": "found", "query": "x", "normalized": "x", "actuator": a, "notes": [TOL]}
    return ToolTrace(tool="get_actuator", params={"part_number": "x"}, result=res)


PAIR = [found(A764), found(A765)]


def bad(answer: str, query: str = "q", **kw: Any) -> list[str]:
    return R.unverified_numbers(answer, PAIR, query, **kw)


def test_wrong_column_with_unit_fires() -> None:
    # 30 is a real value of 764A00, but it is its speed, not a current
    assert bad(f"{P764}: FLA 30 A") == ["30"]
    assert R.build_result(f"{P764}: FLA 30 A", PAIR, "q").guard_triggered


def test_right_column_passes() -> None:
    ans = f"{P764}: FLA 6.5 A, LRA 7.3 A, 750 Nm, 6,650 in-lbs, 180 W, 25%, 30 s, 12 cycles/h."
    assert bad(ans) == []
    assert bad(f"{P764}: 840 starts/h") == []


def test_same_value_from_other_products_field_fails() -> None:
    assert bad(f"{P764}: speed 108 s") == ["108"]  # 108 s is 765B00's speed
    assert bad(f"{P764}: FLA 7 A") == ["7"]  # 7 A is 765B00's FLA
    assert bad(f"{P765}: speed 108 s") == []


def test_unit_outside_map_keeps_product_rule() -> None:
    assert bad(f"{P764}: 30 Hz") == []  # 30 is one of its values; Hz is not in the map
    assert bad(f"{P764}: 7 V") == ["7"]  # product rule: 7 is not a 764A00 value
    assert bad(f"{P764} reaches 30") == []  # no unit


def test_user_typed_figure_passes() -> None:
    assert bad(f"{P764}: FLA 9 A", query="I have a 9 A breaker") == []
    assert bad(f"{P764}: FLA 9 A", user_history="9 A supply") == []


def test_spanish_units_and_decimal_comma() -> None:
    assert bad(f"{P764}: corriente 6,5 amperios, 30 segundos, 180 vatios") == []
    assert bad(f"{P764}: corriente 30 amperios") == ["30"]
    assert bad(f"{P764}: 12 ciclos por hora, 840 arranques por hora") == []
    assert bad(f"{P764}: 12 arranques/h") == ["12"]


@pytest.mark.parametrize("sep", ["", " ", " "])
def test_unit_spacing_variants(sep: str) -> None:
    assert bad(f"{P764}: FLA 30{sep}A") == ["30"]
    assert bad(f"{P764}: torque 6650{sep}in-lbs") == []
    assert bad(f"{P764}: torque 750{sep}in-lbs") == ["750"]  # 750 is Nm


def test_referent_binding() -> None:
    assert bad("It draws 30 A.", referent=P764) == ["30"]
    assert bad("It draws 6.5 A.", referent=P764) == []


def test_notes_tolerance_passes() -> None:
    assert bad(f"{P764}: FLA 6.5 A, voltage tolerance ±10%") == []
    assert bad(f"{P764}: duty cycle 25%") == []
    assert bad(f"{P764}: duty cycle 12%") == ["12"]  # 12 is cycles/h, not duty


def test_figure_without_unit_unchanged() -> None:
    assert bad(f"{P764}: FLA 30") == []
    assert bad(f"{P764}: FLA 9") == ["9"]


def test_unbound_figure_keeps_global_rule() -> None:
    assert bad("There are 108 s somewhere") == []  # no part number: anywhere in the trace
    assert bad("There are 9 s somewhere") == ["9"]
