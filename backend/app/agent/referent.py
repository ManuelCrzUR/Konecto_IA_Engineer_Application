"""Follow-up referent resolution (D-47). Pure, no I/O.

Contract:
- referent_candidates(history) -> list[str]
    Unique part numbers (in order) of the most recent assistant turn that has any.
- resolve_referent(query, history) -> str | None
    The part number a follow-up ("and its power?") refers to: the query names no
    part number AND the last answer with products showed exactly one. Else None.
"""

from __future__ import annotations

import re

from app.agent.numbers import PN_RE as _PN  # the same token the number guard uses
from app.domain.conversation import HistoryTurn

# A partial or model-only mention ("765A", "the 767") also names a product: it is not a
# follow-up about the one shown before, so it must not be bound to that one.
_PARTIAL_PN = re.compile(r"\b76\d(?:[A-Z]\d{0,2})?\b", re.IGNORECASE)


def query_names_part_number(query: str) -> bool:
    q = query or ""
    return _PN.search(q) is not None or _PARTIAL_PN.search(q) is not None


def referent_candidates(history: list[HistoryTurn] | None) -> list[str]:
    for turn in reversed(history or []):
        if turn.role == "assistant" and turn.part_numbers:
            return list(dict.fromkeys(turn.part_numbers))
    return []


def resolve_referent(query: str, history: list[HistoryTurn] | None) -> str | None:
    if query_names_part_number(query):
        return None
    candidates = referent_candidates(history)
    return candidates[0] if len(candidates) == 1 else None
