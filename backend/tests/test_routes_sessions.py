"""GET /api/sessions and /api/sessions/{id}/messages on a minimal app (real Postgres)."""

import uuid
from collections.abc import Iterator

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.api import routes_sessions
from app.api.deps import get_conn
from app.api.errors import install_error_handlers
from app.db import sessions_repo as repo
from app.domain.models import Actuator, Product, ToolTrace
from tests.conftest import act_as, get_test_db_url


@pytest.fixture
def client(pg, dev_user) -> Iterator[TestClient]:
    app = FastAPI()
    app.include_router(routes_sessions.router, prefix="/api")
    install_error_handlers(app)

    url = get_test_db_url()

    def _conn() -> Iterator[psycopg.Connection]:
        with psycopg.connect(url, autocommit=True, row_factory=dict_row) as conn:
            yield conn

    app.dependency_overrides[get_conn] = _conn
    act_as(app, dev_user)
    with TestClient(app) as c:
        yield c


def _product(golden_rows: list[dict]) -> Product:
    return Product.from_actuator(Actuator.model_validate(golden_rows[0]), notes=["n"])


def test_empty_list(client):
    r = client.get("/api/sessions")
    assert r.status_code == 200
    assert r.json() == []


def test_sessions_most_recent_first(client, pg, dev_user):
    a = repo.create_session(pg, "older", dev_user.id)
    b = repo.create_session(pg, "newer", dev_user.id)
    ids = [s["id"] for s in client.get("/api/sessions").json()]
    assert ids == [str(b.id), str(a.id)]

    repo.add_message(pg, a.id, "user", "bump")
    ids = [s["id"] for s in client.get("/api/sessions").json()]
    assert ids == [str(a.id), str(b.id)]


def test_limit_param(client, pg, dev_user):
    for i in range(3):
        repo.create_session(pg, f"s{i}", dev_user.id)
    assert len(client.get("/api/sessions", params={"limit": 1}).json()) == 1
    assert len(client.get("/api/sessions").json()) == 3


@pytest.mark.parametrize("limit", [0, 201])
def test_limit_out_of_range_is_422(client, limit):
    r = client.get("/api/sessions", params={"limit": limit})
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_long_first_query_title_is_truncated(client, pg, dev_user):
    repo.create_session(pg, "¿Qué actuador necesito para una válvula muy grande? " * 4, dev_user.id)
    (s,) = client.get("/api/sessions").json()
    assert len(s["title"]) <= repo.TITLE_MAX
    assert s["title"].endswith("…")


def test_other_users_sessions_not_listed(client, pg, dev_user, plain_user):
    repo.create_session(pg, "ajena", user_id=plain_user.id)
    mine = repo.create_session(pg, "mia", dev_user.id)
    listed = client.get("/api/sessions").json()
    assert [s["id"] for s in listed] == [str(mine.id)]


def test_messages_oldest_first_with_products_and_trace(client, pg, dev_user, golden_rows):
    s = repo.create_session(pg, "t", dev_user.id)
    product = _product(golden_rows)
    trace = ToolTrace(
        tool="search_actuators",
        params={"min_torque": 100, "unit": "Nm"},
        result={"matches": [{"pn": "x", "n": [1, 2.5, None]}]},
        duration_ms=12.5,
    )
    stored_user = repo.add_message(pg, s.id, "user", "pregunta")
    stored_asst = repo.add_message(pg, s.id, "assistant", "respuesta", [product], [trace])

    r = client.get(f"/api/sessions/{s.id}/messages")
    assert r.status_code == 200
    body = r.json()
    assert [m["content"] for m in body] == ["pregunta", "respuesta"]
    assert [m["role"] for m in body] == ["user", "assistant"]
    assert body[0]["id"] == stored_user.id
    assert body[1]["id"] == stored_asst.id
    assert body[1]["products"][0]["part_number"] == product.part_number
    assert body[1]["products"][0]["fields"] == product.fields
    assert body[1]["trace"][0]["tool"] == "search_actuators"
    assert body[1]["trace"][0]["params"] == trace.params
    assert body[1]["trace"][0]["result"] == trace.result
    assert body[1]["trace"][0]["duration_ms"] == trace.duration_ms
    assert body[0]["products"] == [] and body[0]["trace"] == []


def test_messages_unknown_session_is_404(client):
    missing = uuid.uuid4()
    r = client.get(f"/api/sessions/{missing}/messages")
    assert r.status_code == 404
    body = r.json()
    assert body["error"] == "session_not_found"
    assert str(missing) in body["detail"]


def test_messages_of_other_user_session_is_404(client, pg, plain_user):
    s = repo.create_session(pg, "ajena", user_id=plain_user.id)
    r = client.get(f"/api/sessions/{s.id}/messages")
    assert r.status_code == 404
    assert r.json()["error"] == "session_not_found"


def test_messages_malformed_id_is_422(client):
    r = client.get("/api/sessions/no-es-uuid/messages")
    assert r.status_code == 422
    assert r.json()["error"] == "validation_error"


def test_search_returns_match(client, pg, dev_user):
    s = repo.create_session(pg, "Chat", dev_user.id)
    repo.add_message(pg, s.id, "assistant", "The torque is 6650 in-lbs")
    repo.create_session(pg, "unrelated", dev_user.id)
    body = client.get("/api/sessions", params={"q": "TORQUE"}).json()
    assert len(body) == 1 and body[0]["id"] == str(s.id)
    assert body[0]["match"] == {"where": "message", "snippet": "The torque is 6650 in-lbs"}


def test_blank_q_is_plain_listing(client, pg, dev_user):
    repo.create_session(pg, "a", dev_user.id)
    for q in ("", "   "):
        body = client.get("/api/sessions", params={"q": q}).json()
        assert len(body) == 1 and body[0]["match"] is None
    assert client.get("/api/sessions").json()[0]["match"] is None


@pytest.mark.parametrize("limit", [0, 201])
def test_search_limit_bounds(client, limit):
    assert client.get("/api/sessions", params={"q": "a", "limit": limit}).status_code == 422
