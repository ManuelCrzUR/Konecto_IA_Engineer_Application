"""Number and part-number guard (D-26, D-38, D-44, D-51). Pure code, no LLM.

Input:  `answer` (LLM text), `trace` (ToolTrace list; `result` is the tool's JSON
        dict), `query` (user message), `user_history` (what the USER typed before;
        earlier assistant turns never count), `referent` (D-47).
Output: lists of figures / part numbers of the answer that no tool result supports.

Contract:
- extract_numbers(text) -> list[str]: the figures to verify (app/agent/numbers.py):
    digit tokens as written and number words 0..20 (English, Spanish), after blanking
    part numbers and the family name. Only list ordinals, the "90" of a 90 degree
    stroke and tokens inside part numbers need no source (D-44).
- allowed_numbers(trace, query, user_history="") -> set[float]
    Every reading of every token in dict keys and values of every trace result and
    params, the query and user_history, the model size of each traced part number,
    and the counts of what the tools returned.
- unverified_numbers(answer, trace, query, user_history="", *, referent=None) -> list[str]
    Product binding (D-44): a figure is bound to the nearest PRECEDING part-number
    mention in its sentence or line (a table row is one line); with no part number in
    the whole answer it is bound to the referent. If its own sentence names none but
    the WHOLE answer mentions exactly one distinct traced product, it is bound to that
    product (D-51 addendum); with two or more, such a figure keeps the global rule (no
    guessing). A bound figure must be a reading of THAT product's values or notes (not
    another product's), or typed by the user (even with a unit: documented trust,
    D-40), or a count WITHOUT a unit from the D-51 map. Field binding (D-51): if a unit
    follows a bound figure directly (units.py: spaces, markdown emphasis), it must be a
    reading of that product's fields with that unit, or of its notes. Units outside the
    map (Hz, V, none) keep the product rule. Unbound figures keep the global rule.
    Small talk (empty trace): every figure is unverified unless the user typed it.
- unverified_part_numbers(answer, trace, query, user_history="") -> list[str]
    Normalized part-number-like tokens that are neither equal to nor a prefix of one
    found in the trace, the query or user_history.
"""

from __future__ import annotations

import json
import re

from app.agent import numbers
from app.agent.guard_values import (
    bound_values,
    counts,
    pn_tokens,
    product_fields,
    product_values,
    readings,
    unit_values,
    user_numbers,
    walk,
)
from app.agent.numbers import PN_RE as _PN
from app.agent.numbers import token_values
from app.agent.units import unit_key
from app.domain.models import ToolTrace

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n")
_product_values = product_values  # response.py imports this name


def extract_numbers(text: str) -> list[str]:
    return [f.token for f in numbers.figures(text)]


def allowed_numbers(trace: list[ToolTrace], query: str, user_history: str = "") -> set[float]:
    toks: list[str] = []
    for t in trace:
        toks += walk(t.params) + walk(t.result)
    out = user_numbers(query, user_history) | readings(toks)
    # A model size ("the 764") names a product a tool returned; it is not a figure.
    for t in trace:
        for pn in pn_tokens(f"{t.params} {t.result}"):
            out.add(float(pn[:3]))
    return out | counts(trace)


def _sole_product(mentions: list[re.Match[str]], by_pn: dict[str, set[float]]) -> str | None:
    """The one traced product the whole answer mentions (None: none, several or untraced)."""
    keys: set[str] = set()
    for m in mentions:
        mention = pn_tokens(m.group(0))[0]
        hit = {pn for pn in by_pn if pn.startswith(mention)}
        if not hit:
            return None
        keys |= hit
    return next(iter(keys)) if len(keys) == 1 else None


def unverified_numbers(
    answer: str,
    trace: list[ToolTrace],
    query: str,
    user_history: str = "",
    *,
    referent: str | None = None,
) -> list[str]:
    allowed = allowed_numbers(trace, query, user_history)
    user = user_numbers(query, user_history)
    by_pn = product_values(trace)
    by_fields = product_fields(trace)
    cnt = counts(trace)  # valid in any sentence, also next to a part number
    mentions = list(_PN.finditer(answer))
    starts = [0] + [m.end() for m in _SENTENCE_END.finditer(answer)]
    ref = pn_tokens(referent) if referent else []
    sole = _sole_product(mentions, by_pn) if mentions else None
    bad: list[str] = []
    for f in numbers.figures(answer):
        vals = token_values(f.token)
        after = answer[f.end :]
        if vals & user or (vals & cnt and unit_key(after) is None):
            continue
        seg = max(s for s in starts if s <= f.start)
        near = [m for m in mentions if m.start() >= seg and m.end() <= f.start]
        pn = pn_tokens(near[-1].group(0))[0] if near else None
        if pn is None:
            sentence_has_pn = any(seg <= m.start() < _line_end(answer, f.end) for m in mentions)
            pn = sole if not sentence_has_pn else None
        if pn is None and not mentions:
            pn = ref[0] if ref else None
        bound = bound_values(by_pn, pn) if pn else None
        if bound is not None and pn:
            by_unit = unit_values(by_fields, pn, after)
            bound = bound if by_unit is None else by_unit
        if not vals & (allowed if bound is None else bound):
            bad.append(f.token)
    return bad


def _line_end(text: str, pos: int) -> int:
    m = _SENTENCE_END.search(text, pos)
    return m.start() if m else len(text)


def unverified_part_numbers(
    answer: str, trace: list[ToolTrace], query: str, user_history: str = ""
) -> list[str]:
    known = pn_tokens(query) + pn_tokens(user_history)
    for t in trace:
        known += pn_tokens(json.dumps([t.params, t.result], default=str))
    return [p for p in pn_tokens(answer) if not any(k.startswith(p) for k in known)]
