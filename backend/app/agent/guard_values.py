"""Value lookups of the number guard (D-44, D-51). Pure code, no LLM.

Input:  ToolTrace lists, text fragments.
Output: sets of float readings per trace, per product and per product field.
Used by guard.py, which keeps the rules; this module only collects values.
"""

from __future__ import annotations

from typing import Any

from app.agent import numbers
from app.agent.numbers import PN_RE as _PN
from app.agent.numbers import token_values
from app.agent.products import traced_products
from app.agent.units import unit_key
from app.domain.models import ToolTrace

_COUNTED_LISTS = ("matches", "candidates", "suggestions")
_NOTES = "<notes>"  # pseudo field key: the table notes of a product


def walk(obj: Any) -> list[str]:
    """Numeric tokens inside every value of a nested structure (bools ignored)."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, int | float):
        return [format(obj, "f")]
    if isinstance(obj, str):
        return numbers.tokens(obj)
    if isinstance(obj, dict):
        return [n for k, v in obj.items() for n in numbers.tokens(str(k)) + walk(v)]
    if isinstance(obj, list | tuple):
        return [n for v in obj for n in walk(v)]
    return []


def readings(tokens: list[str]) -> set[float]:
    return {v for tok in tokens for v in token_values(tok)}


def user_numbers(query: str, user_history: str) -> set[float]:
    return readings(numbers.tokens(query) + numbers.tokens(user_history))


def pn_tokens(text: str) -> list[str]:
    return [m.upper().rstrip("*").removesuffix("/A") for m in _PN.findall(text)]


def norm_pn(raw: dict[str, Any]) -> str:
    return str(raw["part_number"]).upper().removesuffix("/A")


def counts(trace: list[ToolTrace]) -> set[float]:
    """Counts of what the tools returned ("I found 3 options") come from the data, not memory."""
    out = {float(len(product_values(trace)))}
    for t in trace:
        if isinstance(t.result, dict):
            for key in _COUNTED_LISTS:
                if isinstance(t.result.get(key), list):
                    out.add(float(len(t.result[key])))
    return out


def product_values(trace: list[ToolTrace]) -> dict[str, set[float]]:
    """Normalized part number -> every reading of that product's own values and notes."""
    out: dict[str, set[float]] = {}
    for raw, notes in traced_products(trace):
        pn = norm_pn(raw)
        out.setdefault(pn, {float(pn[:3])}).update(readings(walk(raw) + walk(notes)))
    return out


def product_fields(trace: list[ToolTrace]) -> dict[str, dict[str, set[float]]]:
    """Normalized part number -> field key -> readings of that field (notes under _NOTES)."""
    out: dict[str, dict[str, set[float]]] = {}
    for raw, notes in traced_products(trace):
        fields = out.setdefault(norm_pn(raw), {})
        for k, v in raw.items():
            fields.setdefault(k, set()).update(readings(walk(v)))
        fields.setdefault(_NOTES, set()).update(readings(walk(notes)))
    return out


def bound_values(by_pn: dict[str, set[float]], mention: str) -> set[float] | None:
    """Values of the traced products a part-number mention names (None: no such product)."""
    hits = [v for pn, v in by_pn.items() if pn.startswith(mention)]
    return set().union(*hits) if hits else None


def unit_values(
    by_fields: dict[str, dict[str, set[float]]], mention: str, text: str
) -> set[float] | None:
    """D-51: readings of the mentioned product's fields in the unit right after a figure
    (plus its notes). None when no unit from the map follows or no such product."""
    unit = unit_key(text)
    hits = [f for pn, f in by_fields.items() if pn.startswith(mention)]
    if unit is None or not hits:
        return None
    return {v for f in hits for key, vals in f.items() if key == _NOTES or unit(key) for v in vals}
