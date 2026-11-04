"""sessions_repo against a real Postgres (skipped when unreachable)."""

import os
import uuid

import psycopg
import pytest

from app.db import sessions_repo as repo
from app.domain.models import Actuator, Product, ToolTrace
from tests.conftest import DEFAULT_TEST_URL


def _product(golden_rows: list[dict]) -> Product:
    return Product.from_actuator(Actuator.model_validate(golden_rows[0]), notes=["n"])


def test_create_get_roundtrip(pg):
    s = repo.create_session(pg, "Hello")
    assert s.title == "Hello" and s.user_id is None
    assert repo.get_session(pg, s.id) == s


def test_get_unknown_returns_none(pg):
    assert repo.get_session(pg, uuid.uuid4()) is None


def test_list_ordered_by_updated_desc(pg):
    a = repo.create_session(pg, "a")
    b = repo.create_session(pg, "b")
    assert [s.id for s in repo.list_sessions(pg)] == [b.id, a.id]
    repo.add_message(pg, a.id, "user", "hi")
    assert [s.id for s in repo.list_sessions(pg)] == [a.id, b.id]
    assert len(repo.list_sessions(pg, limit=1)) == 1


def test_user_isolation(pg):
    s = repo.create_session(pg, "mine", user_id="a")
    assert repo.get_session(pg, s.id, user_id="a") == s
    assert repo.get_session(pg, s.id) is None
    assert repo.get_session(pg, s.id, user_id="b") is None
    assert [x.id for x in repo.list_sessions(pg, user_id="a")] == [s.id]
    assert repo.list_sessions(pg) == []
    assert repo.list_sessions(pg, user_id="b") == []


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("  hello   \n world\t!  ", "hello world !"),
        ("x" * 200, "x" * (repo.TITLE_MAX - 1) + "…"),
        ("x" * repo.TITLE_MAX, "x" * repo.TITLE_MAX),
        ("ñ" * 60, "ñ" * (repo.TITLE_MAX - 1) + "…"),
        ("¿Qué actuador necesito? " * 5, None),
    ],
)
def test_title_trimming(pg, raw, expected):
    s = repo.create_session(pg, raw)
    assert len(s.title) <= repo.TITLE_MAX
    if expected is not None:
        assert s.title == expected
    else:
        assert s.title.endswith("…") and "  " not in s.title


def test_messages_oldest_first(pg):
    s = repo.create_session(pg, "t")
    for i in range(3):
        repo.add_message(pg, s.id, "user" if i % 2 == 0 else "assistant", f"m{i}")
    assert [m.content for m in repo.list_messages(pg, s.id)] == ["m0", "m1", "m2"]


def test_products_and_trace_roundtrip(pg, golden_rows):
    s = repo.create_session(pg, "t")
    product = _product(golden_rows)
    trace = ToolTrace(
        tool="search_actuators",
        params={"min_torque": 100, "unit": "Nm"},
        result={"matches": [{"pn": "x", "n": [1, 2.5, None]}], "ok": True},
        duration_ms=12.5,
    )
    stored = repo.add_message(pg, s.id, "assistant", "ans", [product], [trace])
    assert stored.products == [product] and stored.trace == [trace]
    (read,) = repo.list_messages(pg, s.id)
    assert read == stored
    assert read.products[0] == product and read.trace[0] == trace


def test_defaults_are_empty_lists(pg):
    s = repo.create_session(pg, "t")
    m = repo.add_message(pg, s.id, "user", "q")
    assert m.products == [] and m.trace == []


def test_invalid_role_rejected_by_db(pg):
    s = repo.create_session(pg, "t")
    with pytest.raises(psycopg.errors.CheckViolation):
        repo.add_message(pg, s.id, "system", "x")  # type: ignore[arg-type]
    assert repo.list_messages(pg, s.id) == []


def test_unknown_session_fk_rolls_back(pg):
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        repo.add_message(pg, uuid.uuid4(), "user", "x")


def test_persistence_across_connections(pg, golden_rows):
    s = repo.create_session(pg, "persist")
    repo.add_message(pg, s.id, "assistant", "kept", [_product(golden_rows)])
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    with psycopg.connect(url) as fresh:
        assert repo.get_session(fresh, s.id) is not None
        (m,) = repo.list_messages(fresh, s.id)
    assert m.content == "kept" and m.products == [_product(golden_rows)]
