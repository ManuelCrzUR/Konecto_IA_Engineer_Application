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
    the whole answer it is bound to the referent. A bound figure must be a reading of
    THAT product's values or notes (not another product's), or typed by the user, or a
    count. Field binding (D-51): if a unit follows a bound figure directly (optional
    single or non-breaking space), it must be a reading of that product's fields with
    that unit (see units.py), or of its notes. Units outside the map (Hz, V, none) keep
    the product rule. Unbound figures keep the global rule (anywhere in the trace).
    Small talk (empty trace): every figure is unverified unless the user typed it.
- unverified_part_numbers(answer, trace, query, user_history="") -> list[str]
    Normalized part-number-like tokens that are neither equal to nor a prefix of one
    found in the trace, the query or user_history.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.agent import numbers
from app.agent.numbers import PN_RE as _PN
from app.agent.numbers import token_values
from app.agent.products import traced_products
from app.agent.units import unit_key
from app.domain.models import ToolTrace

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n")
_COUNTED_LISTS = ("matches", "candidates", "suggestions")
_NOTES = "<notes>"  # pseudo field key: the table notes of a product
_SP = r"[  ]?"


def extract_numbers(text: str) -> list[str]:
    return [f.token for f in numbers.figures(text)]


def _walk(obj: Any) -> list[str]:
    """Numeric tokens inside every value of a nested structure (bools ignored)."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, int | float):
        return [format(obj, "f")]
    if isinstance(obj, str):
        return numbers.tokens(obj)
    if isinstance(obj, dict):
        return [n for k, v in obj.items() for n in numbers.tokens(str(k)) + _walk(v)]
    if isinstance(obj, list | tuple):
        return [n for v in obj for n in _walk(v)]
    return []


def _readings(tokens: list[str]) -> set[float]:
    return {v for tok in tokens for v in token_values(tok)}


def _user_numbers(query: str, user_history: str) -> set[float]:
    return _readings(numbers.tokens(query) + numbers.tokens(user_history))


def _pn_tokens(text: str) -> list[str]:
    return [m.upper().rstrip("*").removesuffix("/A") for m in _PN.findall(text)]


def _norm_pn(raw: dict[str, Any]) -> str:
    return str(raw["part_number"]).upper().removesuffix("/A")


def allowed_numbers(trace: list[ToolTrace], query: str, user_history: str = "") -> set[float]:
    toks: list[str] = []
    for t in trace:
        toks += _walk(t.params) + _walk(t.result)
    out = _user_numbers(query, user_history) | _readings(toks)
    # A model size ("the 764") names a product a tool returned; it is not a figure.
    for t in trace:
        for pn in _pn_tokens(f"{t.params} {t.result}"):
            out.add(float(pn[:3]))
    return out | _counts(trace)


def _counts(trace: list[ToolTrace]) -> set[float]:
    """Counts of what the tools returned ("I found 3 options") come from the data, not memory."""
    out = {float(len(_product_values(trace)))}
    for t in trace:
        if isinstance(t.result, dict):
            for key in _COUNTED_LISTS:
                if isinstance(t.result.get(key), list):
                    out.add(float(len(t.result[key])))
    return out


def _product_values(trace: list[ToolTrace]) -> dict[str, set[float]]:
    """Normalized part number -> every reading of that product's own values and notes."""
    out: dict[str, set[float]] = {}
    for raw, notes in traced_products(trace):
        pn = _norm_pn(raw)
        out.setdefault(pn, {float(pn[:3])}).update(_readings(_walk(raw) + _walk(notes)))
    return out


def _product_fields(trace: list[ToolTrace]) -> dict[str, dict[str, set[float]]]:
    """Normalized part number -> field key -> readings of that field (notes under _NOTES)."""
    out: dict[str, dict[str, set[float]]] = {}
    for raw, notes in traced_products(trace):
        fields = out.setdefault(_norm_pn(raw), {})
        for k, v in raw.items():
            fields.setdefault(k, set()).update(_readings(_walk(v)))
        fields.setdefault(_NOTES, set()).update(_readings(_walk(notes)))
    return out


def _bound_values(by_pn: dict[str, set[float]], mention: str) -> set[float] | None:
    """Values of the traced products a part-number mention names (None: no such product)."""
    hits = [v for pn, v in by_pn.items() if pn.startswith(mention)]
    return set().union(*hits) if hits else None


def _unit_values(
    by_fields: dict[str, dict[str, set[float]]], mention: str, text: str
) -> set[float] | None:
    """D-51: readings of the mentioned product's fields in the unit right after a figure
    (plus its notes). None when no unit from the map follows or no such product."""
    unit = unit_key(text)
    hits = [f for pn, f in by_fields.items() if pn.startswith(mention)]
    if unit is None or not hits:
        return None
    return {v for f in hits for key, vals in f.items() if key == _NOTES or unit(key) for v in vals}


def unverified_numbers(
    answer: str,
    trace: list[ToolTrace],
    query: str,
    user_history: str = "",
    *,
    referent: str | None = None,
) -> list[str]:
    allowed = allowed_numbers(trace, query, user_history)
    user = _user_numbers(query, user_history)
    by_pn = _product_values(trace)
    by_fields = _product_fields(trace)
    counts = _counts(trace)  # valid in any sentence, also next to a part number
    mentions = list(_PN.finditer(answer))
    starts = [0] + [m.end() for m in _SENTENCE_END.finditer(answer)]
    ref_pn = _pn_tokens(referent)[0] if referent and _pn_tokens(referent) else None
    bad: list[str] = []
    for f in numbers.figures(answer):
        vals = token_values(f.token)
        if vals & user or vals & counts:
            continue
        seg = max(s for s in starts if s <= f.start)
        near = [m for m in mentions if m.start() >= seg and m.end() <= f.start]
        pn = _pn_tokens(near[-1].group(0))[0] if near else None
        if pn is None and not mentions:
            pn = ref_pn
        bound = _bound_values(by_pn, pn) if pn else None
        if bound is not None and pn:
            by_unit = _unit_values(by_fields, pn, answer[f.end :])
            bound = bound if by_unit is None else by_unit
        if not vals & (allowed if bound is None else bound):
            bad.append(f.token)
    return bad


def unverified_part_numbers(
    answer: str, trace: list[ToolTrace], query: str, user_history: str = ""
) -> list[str]:
    known = _pn_tokens(query) + _pn_tokens(user_history)
    for t in trace:
        known += _pn_tokens(json.dumps([t.params, t.result], default=str))
    return [p for p in _pn_tokens(answer) if not any(k.startswith(p) for k in known)]
