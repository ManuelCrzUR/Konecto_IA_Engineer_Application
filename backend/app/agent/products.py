"""Products the tools returned, read from the tool trace. Code, not LLM.

Input:  `trace` (one ToolTrace per call; `result` is the tool's JSON dict) and,
        for products_from_trace, the final `answer` text.
Output: traced_products(trace) -> [(actuator dict, table notes)] and
        products_from_trace(trace, answer) -> list[Product].

Contract:
- traced_products: in trace order, the actuators of
    get_actuator with status found / found_no_data -> result["actuator"]
      (notes = result["notes"]);
    search_actuators with status ok -> result["matches"] (notes: the CSA note
      when csa_certified is False, else []).
  ambiguous / not_found / no_match / describe_catalog give nothing. The number
  guard (guard.py) and products_from_trace share this one iteration.
- products_from_trace: those actuators as Product, deduped by part_number. On a
  duplicate the entry with more notes wins (get_actuator carries the table
  notes), keeping the first position. Then filtered by mention (case-insensitive):
  products whose full part number (with or without '/A') appears in the answer; if
  none, products whose 6-char base ('764A00') appears; if none, keep all.
"""

from __future__ import annotations

from typing import Any

from app.agent.tools import CSA_NOTE
from app.domain.models import Actuator, Product, ToolTrace


def traced_products(trace: list[ToolTrace]) -> list[tuple[dict[str, Any], list[str]]]:
    out: list[tuple[dict[str, Any], list[str]]] = []
    for t in trace:
        r = t.result
        if not isinstance(r, dict):
            continue
        if t.tool == "get_actuator" and r.get("status") in ("found", "found_no_data"):
            items = [(r.get("actuator"), list(r.get("notes") or []))]
        elif t.tool == "search_actuators" and r.get("status") == "ok":
            items = [(m, [] if m.get("csa_certified", True) else [CSA_NOTE]) for m in r["matches"]]
        else:
            continue
        out += [
            (raw, notes) for raw, notes in items if isinstance(raw, dict) and "part_number" in raw
        ]
    return out


def products_from_trace(trace: list[ToolTrace], answer: str) -> list[Product]:
    found: dict[str, Product] = {}
    for raw, notes in traced_products(trace):
        prod = Product.from_actuator(Actuator.model_validate(raw), notes)
        prev = found.get(prod.part_number)
        if prev is None or len(prod.notes) > len(prev.notes):
            found[prod.part_number] = prod
    low = answer.lower()
    full = [p for pn, p in found.items() if pn.lower().removesuffix("/a") in low]
    if full:
        return full
    base = [p for pn, p in found.items() if pn[:6].lower() in low]
    return base or list(found.values())
