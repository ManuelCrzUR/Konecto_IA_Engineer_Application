"""Freezes the public signatures fixed in Sprint 1 (task 1.8).

If an implementation changes a contract, this test fails on purpose: update the
contract deliberately (and docs/DECISIONS.md), not by accident.
"""

import inspect

import pytest

from app import bootstrap
from app.agent import agent, prompts, response, tools
from app.api import schemas
from app.db import actuators_repo, connection, sessions_repo
from app.domain.search import SearchFilters
from app.ingestion import pipeline

CONTRACTS = {
    connection: {
        "database_url": [],
        "connect": ["url"],
        "apply_schema": ["conn"],
        "conn_factory": ["url"],
    },
    actuators_repo: {
        "count": ["conn"],
        "upsert_catalog": ["conn", "catalog"],
        "delete_all": ["conn"],
        "get_by_pn": ["conn", "part_number"],
        "find_like": ["conn", "fragment", "limit"],
        "search": ["conn", "filters", "limit"],
        "count_matches": ["conn", "filters"],
        "diagnose_no_match": ["conn", "filters"],
        "catalog_summary": ["conn"],
        "table_notes": ["conn", "table_ids"],
    },
    sessions_repo: {
        "create_session": ["conn", "title", "user_id"],
        "get_session": ["conn", "session_id", "user_id"],
        "list_sessions": ["conn", "user_id", "limit"],
        "add_message": ["conn", "session_id", "role", "content", "products", "trace"],
        "list_messages": ["conn", "session_id"],
    },
    pipeline: {"extract_catalog": ["pdf_path", "escalator"]},
    bootstrap: {"ensure_data": ["conn", "json_path", "pdf_path", "escalator"]},
    tools: {
        "normalize_part_number": ["text"],
        "lookup_actuator": ["conn", "part_number"],
        "search": ["conn", "filters", "limit"],
        "describe": ["conn"],
        "make_tools": ["conn_factory"],
    },
    prompts: {"context_line": ["history"], "build_messages": ["query", "history"]},
    response: {
        "products_from_trace": ["trace", "answer"],
        "extract_numbers": ["text"],
        "token_values": ["token"],
        "allowed_numbers": ["trace", "query", "user_history"],
        "unverified_numbers": ["answer", "trace", "query", "user_history"],
        "unverified_part_numbers": ["answer", "trace", "query", "user_history"],
        "detect_lang": ["query"],
        "template_answer": ["trace", "query"],
        "build_result": ["answer", "trace", "query", "user_history", "model_id"],
    },
    agent: {"run_agent": ["query", "history", "llm", "conn_factory"]},
}

CASES = [(mod, name, params) for mod, fns in CONTRACTS.items() for name, params in fns.items()]


@pytest.mark.parametrize(
    ("module", "name", "params"), CASES, ids=[f"{m.__name__}.{n}" for m, n, _ in CASES]
)
def test_signature(module, name, params):
    fn = getattr(module, name)
    assert list(inspect.signature(fn).parameters) == params


def test_tool_names_fixed():
    assert tools.TOOL_NAMES == ("get_actuator", "search_actuators", "describe_catalog")


def test_api_schema_exports():
    assert set(schemas.__all__) == {
        "ConversationRequest", "ConversationResponse", "ErrorOut", "MessageOut", "SearchMatch",
        "SessionOut",
    }


def test_search_filters_defaults():
    f = SearchFilters()
    assert f.torque_unit == "nm" and f.speed_hz == 60
    assert all(getattr(f, k) is None for k in ("min_torque", "voltage_v", "phase", "service"))
