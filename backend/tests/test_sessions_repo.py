"""sessions_repo against a real Postgres (skipped when unreachable)."""

import uuid

import psycopg
import pytest

from app.db import sessions_repo as repo
from app.db import sessions_search
from app.domain.models import Actuator, Product, ToolTrace
from tests.conftest import get_test_db_url


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


def test_user_isolation(pg, test_users):
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
    url = get_test_db_url()
    with psycopg.connect(url) as fresh:
        assert repo.get_session(fresh, s.id) is not None
        (m,) = repo.list_messages(fresh, s.id)
    assert m.content == "kept" and m.products == [_product(golden_rows)]


# --- search_sessions -------------------------------------------------------


def _search(pg, q, **kw):
    return [(s.title, h.where, h.snippet) for s, h in sessions_search.search_sessions(pg, q, **kw)]


def test_search_title_match(pg):
    repo.create_session(pg, "Torque for 764A")
    repo.create_session(pg, "Other")
    assert _search(pg, "TORQUE") == [("Torque for 764A", "title", "Torque for 764A")]


def test_search_message_match_and_first_message_wins(pg):
    s = repo.create_session(pg, "Chat")
    repo.add_message(pg, s.id, "user", "nothing here")
    repo.add_message(pg, s.id, "assistant", "The Speed is 15 s")
    repo.add_message(pg, s.id, "assistant", "another speed note")
    assert _search(pg, "speed") == [("Chat", "message", "The Speed is 15 s")]


def test_search_title_wins_over_message(pg):
    s = repo.create_session(pg, "speed question")
    repo.add_message(pg, s.id, "user", "speed")
    assert _search(pg, "speed")[0][1] == "title"


def test_search_wildcards_are_literal(pg):
    a = repo.create_session(pg, "100% duty")
    repo.create_session(pg, "1000 duty")
    c = repo.create_session(pg, "a_b")
    repo.create_session(pg, "axb")
    d = repo.create_session(pg, "path")
    repo.add_message(pg, d.id, "user", r"back\slash")
    assert [t for t, _, _ in _search(pg, "100%")] == ["100% duty"]
    assert [t for t, _, _ in _search(pg, "a_b")] == ["a_b"]
    assert [t for t, _, _ in _search(pg, "%")] == ["100% duty"]
    assert [t for t, _, _ in _search(pg, "\\")] == ["path"]
    assert a and c


def test_search_user_scoping(pg, test_users):
    repo.create_session(pg, "shared word", user_id="a")
    repo.create_session(pg, "shared word")
    assert len(sessions_search.search_sessions(pg, "shared", user_id="a")) == 1
    assert len(sessions_search.search_sessions(pg, "shared")) == 1
    assert sessions_search.search_sessions(pg, "shared", user_id="b") == []


def test_search_order_and_limit(pg):
    a = repo.create_session(pg, "x one")
    repo.create_session(pg, "x two")
    repo.add_message(pg, a.id, "user", "bump")
    assert [t for t, _, _ in _search(pg, "x")] == ["x one", "x two"]
    assert len(_search(pg, "x", limit=1)) == 1


def test_search_no_results(pg):
    repo.create_session(pg, "abc")
    assert _search(pg, "zzz") == []


def _busy(pg, sid):
    return pg.execute("SELECT busy_since FROM sessions WHERE id = %s", (sid,)).fetchone()


def test_lock_unlock_and_stale_retake(pg):
    sid = repo.create_session(pg, "t").id
    assert repo.try_lock_session(pg, sid) is not None
    assert repo.try_lock_session(pg, sid) is None
    repo.unlock_session(pg, sid)
    assert repo.try_lock_session(pg, sid) is not None
    pg.execute(
        "UPDATE sessions SET busy_since = now() - interval '3 minutes' WHERE id = %s", (sid,)
    )
    assert repo.try_lock_session(pg, sid) is not None  # stale lock retaken
    repo.unlock_session(pg, sid)
    assert repo.try_lock_session(pg, uuid.uuid4()) is None  # unknown session


def test_slow_turn_cannot_release_a_lock_taken_after_it_went_stale(pg):
    sid = repo.create_session(pg, "t").id
    old = repo.try_lock_session(pg, sid)
    pg.execute(
        "UPDATE sessions SET busy_since = busy_since - interval '3 minutes' WHERE id = %s", (sid,)
    )
    stale = _busy(pg, sid)[0]
    new = repo.try_lock_session(pg, sid)  # turn B retakes the stale lock
    assert old is not None and new is not None and new != stale
    repo.unlock_session(pg, sid, stale)  # turn A finishes late with its old token
    assert _busy(pg, sid)[0] is not None  # B still holds it
    repo.unlock_session(pg, sid, new)
    assert _busy(pg, sid)[0] is None
