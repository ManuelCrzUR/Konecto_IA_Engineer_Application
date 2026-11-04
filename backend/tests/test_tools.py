"""Tests for agent/tools.py against the real catalog in the test Postgres. No LLM."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.agent import tools
from app.db import actuators_repo as repo
from app.db import connection
from app.domain.models import Catalog
from app.domain.search import SearchFilters
from tests.conftest import DEFAULT_TEST_URL, PROCESSED_JSON

CATALOG = Catalog.model_validate_json(PROCESSED_JSON.read_text())
SCHEMAS = Path(__file__).parent / "fixtures" / "tool_schemas.json"


@pytest.fixture
def db(pg):
    repo.upsert_catalog(pg, CATALOG)
    return pg


# ---- normalize (pure) -------------------------------------------------------
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (" 764a00-11300000/a ", "764A00-11300000/A"),
        ("764A00-11300000", "764A00-11300000/A"),
        ("766A00-11320000/A*", "766A00-11320000/A"),
        ("764a", "764A"),
        ("764A0011300000", "764A00-11300000/A"),
        ("764 A00 11300000", "764A00-11300000/A"),
        ("764a00", "764A00"),
        ("", ""),
        ("hello world", "HELLOWORLD"),
    ],
)
def test_normalize(raw, expected):
    assert tools.normalize_part_number(raw) == expected


# ---- lookup -----------------------------------------------------------------
def test_exact_found(db):
    r = tools.lookup_actuator(db, "764a00-11300000")
    assert r.status == "found"
    assert r.normalized == "764A00-11300000/A"
    assert r.actuator is not None and r.actuator.part_number == "764A00-11300000/A"
    assert CSA_NOTE not in r.notes
    assert r.notes  # table notes (tolerances etc.)


CSA_NOTE = tools.CSA_NOTE


def test_found_no_data(db):
    r = tools.lookup_actuator(db, "761A00-11330C00/A")
    assert r.status == "found_no_data"
    assert r.actuator is not None and not r.actuator.has_data


def test_na_rows_are_the_four_3phase_ones(db):
    n = [
        a.part_number[:4] for a in CATALOG.rows if a.table_id == "T3_wp_220v_3ph" and not a.has_data
    ]
    assert sorted(n) == ["761A", "761B", "762A", "762B"]


def test_csa_note(db):
    r = tools.lookup_actuator(db, "766A00-11320000/A")
    assert r.status == "found"
    assert r.actuator is not None and r.actuator.csa_certified is False
    assert CSA_NOTE in r.notes


@pytest.mark.parametrize("q", ["764", "764A00"])
def test_partial_ambiguous(db, q):
    r = tools.lookup_actuator(db, q)
    assert r.status == "ambiguous"
    assert r.actuator is None
    pns = [c.part_number for c in r.candidates]
    assert pns == sorted(pns)
    assert all(p.startswith(r.normalized) for p in pns)


def test_764a00_candidates_detail(db):
    r = tools.lookup_actuator(db, "764A00")
    got = {(c.voltage, c.phase) for c in r.candidates}
    assert got == {("110V", 1), ("220V", 1), ("220V", 3)}
    assert len(r.candidates) == 3
    assert all(c.enclosure == "weatherproof" and c.has_data for c in r.candidates)


def test_unique_prefix_is_found(db):
    r = tools.lookup_actuator(db, "764X30-11300000")
    assert r.status == "found"
    assert r.actuator is not None and r.actuator.part_number == "764X30-11300000/A"


@pytest.mark.parametrize("q", ["999Z", "hello", "", "  ", "7"])
def test_not_found(db, q):
    r = tools.lookup_actuator(db, q)
    assert r.status == "not_found"
    assert isinstance(r.suggestions, list)
    assert r.actuator is None


def test_not_found_close_suggestions(db):
    r = tools.lookup_actuator(db, "768A00")
    assert r.status == "not_found"
    assert r.suggestions and len(r.suggestions) <= 5
    assert all(p.startswith("76") for p in r.suggestions)


# ---- search -----------------------------------------------------------------
def test_search_ok_tightest_first_and_limit(db):
    f = SearchFilters(min_torque=100, voltage_v=110, enclosure="weatherproof", service="on_off")
    r = tools.search(db, f, limit=3)
    assert r.status == "ok"
    assert r.filters == f
    assert len(r.matches) == 3 <= r.total
    torques = [a.onoff_torque_nm for a in r.matches]
    assert all(t is not None and t >= 100 for t in torques)
    assert torques == sorted(torques)
    expected = sorted(
        a.onoff_torque_nm
        for a in CATALOG.rows
        if a.voltage == "110V"
        and a.enclosure == "weatherproof"
        and a.onoff_torque_nm is not None
        and a.onoff_torque_nm >= 100
    )
    assert r.total == len(expected)
    assert torques == expected[:3]


def test_search_impossible_torque(db):
    r = tools.search(db, SearchFilters(min_torque=1_000_000, voltage_v=110, service="on_off"))
    assert r.status == "no_match" and r.matches == []
    assert r.no_match is not None
    assert r.no_match.blocking == ["min_torque"]
    assert not r.no_match.out_of_catalog
    assert r.no_match.closest["min_torque"] > 0


def test_search_out_of_catalog(db):
    r = tools.search(db, SearchFilters(voltage_v=24, enclosure="weatherproof"))
    assert r.status == "no_match"
    assert r.no_match is not None and r.no_match.out_of_catalog is True


def test_search_unit_uses_printed_columns(db):
    f = {"voltage_v": 110, "service": "on_off", "enclosure": "weatherproof"}
    in_lbs = tools.search(db, SearchFilters(min_torque=700, torque_unit="in_lbs", **f), limit=50)
    nm = tools.search(db, SearchFilters(min_torque=700, torque_unit="nm", **f), limit=50)
    assert in_lbs.status == "ok"
    assert all((a.onoff_torque_in_lbs or 0) >= 700 for a in in_lbs.matches)
    assert nm.total != in_lbs.total or [a.part_number for a in nm.matches] != [
        a.part_number for a in in_lbs.matches
    ]
    assert all((a.onoff_torque_nm or 0) >= 700 for a in nm.matches)


def test_describe(db):
    s = tools.describe(db)
    assert s.total_rows == 68
    assert s.rows_without_data == 4
    assert s.combinations


# ---- make_tools -------------------------------------------------------------
@pytest.fixture
def toolset(db):
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    return {t.name: t for t in tools.make_tools(connection.conn_factory(url))}


def test_make_tools_names_and_order(toolset):
    assert tuple(toolset) == tools.TOOL_NAMES
    assert all(t.description for t in toolset.values())


def test_tools_invoke_return_dicts(toolset):
    got = toolset["get_actuator"].invoke({"part_number": "764A00-11300000/A"})
    assert isinstance(got, dict) and got["status"] == "found"
    assert got["actuator"]["part_number"] == "764A00-11300000/A"

    found = toolset["search_actuators"].invoke(
        {"min_torque": 100, "voltage_v": 110, "service": "on_off"}
    )
    assert isinstance(found, dict) and found["status"] == "ok"
    assert found["filters"]["min_torque"] == 100

    empty = toolset["search_actuators"].invoke({})
    assert empty["status"] == "ok"  # no constraint: everything matches

    summary = toolset["describe_catalog"].invoke({})
    assert isinstance(summary, dict) and summary["total_rows"] == 68
    json.dumps([got, found, summary])  # JSON-serializable


def test_tool_schemas_snapshot(toolset):
    current = {n: t.tool_call_schema.model_json_schema() for n, t in toolset.items()}
    assert current == json.loads(SCHEMAS.read_text())


def test_as_printed_drops_trailing_zero_only() -> None:
    from app.agent.tools import as_printed

    assert as_printed({"a": 750.0, "b": [1.1, 2.0], "c": {"d": 0.0}, "e": True, "f": None}) == {
        "a": 750, "b": [1.1, 2], "c": {"d": 0}, "e": True, "f": None
    }
    assert isinstance(as_printed(750.0), int)


def test_tool_output_has_printed_integers(db) -> None:
    import os

    from app.agent.tools import make_tools
    from app.db.connection import conn_factory
    from tests.conftest import DEFAULT_TEST_URL

    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    out = make_tools(conn_factory(url))[0].invoke({"part_number": "764A00-11300000/A"})
    torque = out["actuator"]["onoff_torque_nm"]
    assert torque == 750 and isinstance(torque, int)


@pytest.mark.parametrize(
    ("raw", "norm"), [("761A001130", "761A00-1130"), ("761a0011", "761A00-11"), ("764A00", "764A00")]
)
def test_normalize_dashless_partial(raw: str, norm: str) -> None:
    from app.agent.tools import normalize_part_number

    assert normalize_part_number(raw) == norm


def test_dashless_partial_resolves_by_prefix(db) -> None:
    from app.agent.tools import lookup_actuator

    r = lookup_actuator(db, "761A001130")
    assert r.status == "found" and r.actuator.part_number == "761A00-11300000/A"
