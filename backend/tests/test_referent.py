"""Referent resolution (D-47): pure functions."""

from app.agent.referent import referent_candidates, resolve_referent
from app.domain.conversation import HistoryTurn


def turn(role: str, pns: list[str] | None = None) -> HistoryTurn:
    return HistoryTurn(role=role, content="x", part_numbers=pns or [])  # type: ignore[arg-type]


def test_single_product_is_referent() -> None:
    h = [turn("user"), turn("assistant", ["764A00-11300000/A"])]
    assert resolve_referent("¿y la potencia?", h) == "764A00-11300000/A"


def test_duplicates_count_once() -> None:
    assert resolve_referent("power?", [turn("assistant", ["P", "P"])]) == "P"


def test_part_number_in_query_wins() -> None:
    h = [turn("assistant", ["764A00-11300000/A"])]
    assert resolve_referent("and 763B00?", h) is None
    assert resolve_referent("and 763b00-11300000/a?", h) is None


def test_several_products_no_referent_but_candidates() -> None:
    h = [turn("assistant", ["A", "B", "C", "A"])]
    assert resolve_referent("and its power?", h) is None
    assert referent_candidates(h) == ["A", "B", "C"]


def test_empty_history() -> None:
    assert resolve_referent("hi", None) is None
    assert resolve_referent("hi", []) is None
    assert referent_candidates([turn("assistant")]) == []


def test_uses_most_recent_assistant_turn_with_products() -> None:
    h = [turn("assistant", ["A", "B"]), turn("assistant", ["C"]), turn("assistant")]
    assert resolve_referent("power?", h) == "C"
