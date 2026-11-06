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

from app.domain.conversation import HistoryTurn

# Same pattern as response.py's part-number token (kept identical on purpose).
PN_PATTERN = r"76\d[A-Z]\d{2}(?:-[0-9A-Z]{8}(?:/A)?)?\*?"
_PN = re.compile(PN_PATTERN, re.IGNORECASE)


def query_names_part_number(query: str) -> bool:
    return _PN.search(query or "") is not None


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
