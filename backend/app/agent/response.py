"""Turns the LLM's text + the tool trace into an AgentResult. Code, not LLM.

Input:  `answer` (LLM text), `trace` (one ToolTrace per tool call, `result` is
        the tool's JSON dict: ActuatorLookup / SearchResult / CatalogSummary
        dumped with mode="json"), `query` (the user's message).
Output: AgentResult(answer, products, trace, guard_triggered).

Contract:
- products_from_trace(trace, answer) -> list[Product]
    Collect actuators, in trace order, deduped by part_number:
      get_actuator with status found / found_no_data -> result["actuator"]
        (Product notes = result["notes"]);
      search_actuators with status ok -> result["matches"] (notes: the CSA
        note when csa_certified is False, else []).
    On a duplicate part number the entry with more notes wins (get_actuator
    carries the table notes), keeping the first position.
    ambiguous / not_found / no_match / describe_catalog give no products.
    Then filter by mention (case-insensitive): products whose full part number
    (with or without '/A') appears in the answer; if none, products whose
    6-char base ('764A00') appears; if none, keep all.
- extract_numbers(text) -> list[str]
    Numeric tokens in `text` after removing every part-number-like token
    (regex r"76\\d[A-Z]\\d{2}(?:-[0-9A-Z]{8}(?:/A)?)?\\*?", case-insensitive)
    and the product family name ("Series 76", "Serie 76", "Série 76"; case-insensitive).
    A token is digits with optional ',' or '.' separators: '1,330', '2.3',
    '17', '2,3'. Returned as written.
- token_values(token) -> set[float]
    All readings of a token: '1,330' -> {1330.0, 1.33}; '2,3' -> {2.3};
    '1.330' -> {1.33, 1330.0}; '17' -> {17.0}; '1,234,567' -> {1234567.0}.
- allowed_numbers(trace, query, user_history="") -> set[float]
    Every reading of every numeric token found in: dict keys ('fla_50hz_a' -> 50) and all values (numbers and
    strings, recursively) of every trace result and params, the query, and
    `user_history` (what the USER typed in earlier turns; earlier assistant
    turns never count). Plus ALWAYS_ALLOWED.
- unverified_numbers(answer, trace, query, user_history="") -> list[str]
    Tokens of extract_numbers(answer) with no reading in allowed_numbers.
- unverified_part_numbers(answer, trace, query, user_history="") -> list[str]
    Part-number-like tokens in the answer (same regex as above, normalized:
    uppercase, no '*' or '/A') that are neither equal to nor a prefix of a
    part-number token found in the trace (params and results), the query or
    `user_history`.
    Catches a part number the LLM made up.
- template_answer(trace, query) -> str
    Deterministic answer built only from the trace, in the query's language
    (detect_lang). Uses the products (part number, voltage, enclosure and the
    printed fields with their units), else the last no_match message / not
    found suggestions / ambiguous candidates, else a short "could not verify,
    please rephrase" line. Every number in it comes from the trace.
- detect_lang(query) -> "es" | "en"   (cheap heuristic: Spanish accents/¿¡ñ
    or common Spanish words -> "es")
- build_result(answer, trace, query, user_history="") -> AgentResult
    (`query` alone drives language detection; `user_history` is passed to the checks.)
    unverified = unverified_numbers + unverified_part_numbers.
    If it is empty: answer unchanged, guard_triggered False.
    Else: answer = template_answer(...), guard_triggered True, and a
    ToolTrace(tool=GUARD_TOOL, params={"unverified": [...], "original_answer":
    answer}, result="template answer used") is appended to the trace.
    products = products_from_trace(trace, final answer).
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from app.agent.tools import CSA_NOTE
from app.domain.conversation import AgentResult
from app.domain.models import Actuator, Product, ToolTrace

GUARD_TOOL = "number_guard"
# Small integers (list counts, "option 2") and the 90° stroke.
ALWAYS_ALLOWED: frozenset[float] = frozenset({*map(float, range(11)), 90.0})

_PN = re.compile(r"76\d[A-Z]\d{2}(?:-[0-9A-Z]{8}(?:/A)?)?\*?", re.IGNORECASE)
_FAMILY = re.compile(r"\bS[eé]ries?[\s-]*76\b", re.IGNORECASE)  # product name, not a figure
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_ES_WORDS = frozenset(
    {"que", "cual", "cuales", "el", "la", "los", "las", "un", "una", "necesito", "quiero"}
    | {"busco", "actuador", "para", "con", "de", "es", "tiene", "hay", "cuanto", "como", "dame"}
    | {"velocidad", "corriente", "donde", "tienen", "muestrame", "cuantos"}
)
_TEXT = {
    "en": {
        "found": "Data from the tables:",
        "nodata": "listed in the tables without data (N/A)",
        "csa": "not CSA certified",
        "notfound": "I could not find that part number.",
        "closest": "Closest part numbers: {x}.",
        "ambig": "That matches several part numbers: {x}. Which one do you mean?",
        "none": "I could not verify an answer from the data. Could you rephrase the question?",
    },
    "es": {
        "found": "Datos de las tablas:",
        "nodata": "figura en las tablas sin datos (N/A)",
        "csa": "sin certificación CSA",
        "notfound": "No encontré ese número de parte.",
        "closest": "Números de parte cercanos: {x}.",
        "ambig": "Coincide con varios números de parte: {x}. ¿Cuál necesitas?",
        "none": "No pude verificar una respuesta con los datos. ¿Puedes reformular la pregunta?",
    },
}


def products_from_trace(trace: list[ToolTrace], answer: str) -> list[Product]:
    found: dict[str, Product] = {}
    for t in trace:
        r = t.result
        if not isinstance(r, dict):
            continue
        if t.tool == "get_actuator" and r.get("status") in ("found", "found_no_data"):
            items = [(r["actuator"], list(r.get("notes") or []))]
        elif t.tool == "search_actuators" and r.get("status") == "ok":
            items = [(m, [] if m.get("csa_certified", True) else [CSA_NOTE]) for m in r["matches"]]
        else:
            continue
        for raw, notes in items:
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


def extract_numbers(text: str) -> list[str]:
    return _NUM.findall(_PN.sub(" ", _FAMILY.sub(" ", text)))


def token_values(token: str) -> set[float]:
    seps = [c for c in token if not c.isdigit()]
    if not seps:
        return {float(token)}
    if len(set(seps)) == 1 and len(seps) > 1:  # '1,234,567': thousands only
        return {float(token.replace(seps[0], ""))}
    last = max(token.rfind(","), token.rfind("."))
    head, tail = token[:last], token[last + 1 :]
    plain = re.sub(r"[.,]", "", head)
    values = {float(f"{plain}.{tail}")}
    if len(seps) == 1 and len(tail) == 3:  # '1,330' may be 1330 or 1.33
        values.add(float(plain + tail))
    return values


def _walk(obj: Any) -> list[str]:
    """Numeric tokens inside every value of a nested structure (bools ignored)."""
    if isinstance(obj, bool) or obj is None:
        return []
    if isinstance(obj, int | float):
        return [format(obj, "f")]
    if isinstance(obj, str):
        return extract_numbers(obj)
    if isinstance(obj, dict):
        return [n for k, v in obj.items() for n in extract_numbers(str(k)) + _walk(v)]
    if isinstance(obj, list | tuple):
        return [n for v in obj for n in _walk(v)]
    return []


def allowed_numbers(trace: list[ToolTrace], query: str, user_history: str = "") -> set[float]:
    tokens = extract_numbers(query) + extract_numbers(user_history)
    for t in trace:
        tokens += _walk(t.params) + _walk(t.result)
    out = set(ALWAYS_ALLOWED)
    for tok in tokens:
        out |= token_values(tok)
    # A model size ("the 764") names a product a tool returned; it is not a figure.
    for t in trace:
        for pn in _pn_tokens(f"{t.params} {t.result}"):
            out.add(float(pn[:3]))
    return out


def unverified_numbers(
    answer: str, trace: list[ToolTrace], query: str, user_history: str = ""
) -> list[str]:
    allowed = allowed_numbers(trace, query, user_history)
    return [n for n in extract_numbers(answer) if not token_values(n) & allowed]


def _pn_tokens(text: str) -> list[str]:
    return [m.upper().rstrip("*").removesuffix("/A") for m in _PN.findall(text)]


def unverified_part_numbers(
    answer: str, trace: list[ToolTrace], query: str, user_history: str = ""
) -> list[str]:
    known = _pn_tokens(query) + _pn_tokens(user_history)
    for t in trace:
        known += _pn_tokens(json.dumps([t.params, t.result], default=str))
    return [p for p in _pn_tokens(answer) if not any(k.startswith(p) for k in known)]


def detect_lang(query: str) -> Literal["es", "en"]:
    if re.search(r"[áéíóúñ¿¡]", query.lower()):
        return "es"
    return "es" if _ES_WORDS & set(re.findall(r"[a-z]+", query.lower())) else "en"


def _fmt(v: float) -> str:
    return str(int(v)) if v == int(v) else str(v)


def _field(key: str, v: float) -> str:
    units = (("_in_lbs", "in-lbs"), ("_nm", "Nm"), ("_pct", "%"), ("_a", "A"), ("_w", "W"))
    unit = next((u for suffix, u in units if key.endswith(suffix)), "s" if "_sec" in key else "")
    label = re.sub(r"_(in_lbs|nm|pct|a|w|sec)(?=_|$)", "", key).replace("_", " ")
    label = re.sub(r"(\d+)hz", r"\1 Hz", label)
    label = re.sub(r"\b(fla|lra)\b", lambda m: m[1].upper(), label)
    label = label.replace("onoff", "on/off").replace("mod ", "mod. ")
    return f"{label} {_fmt(v)}{' ' + unit if unit else ''}"


def template_answer(trace: list[ToolTrace], query: str) -> str:
    tx = _TEXT[detect_lang(query)]
    products = products_from_trace(trace, "")
    if products:
        lines = [tx["found"]]
        for p in products[:5]:
            parts = [f"{p.voltage}", p.enclosure]
            parts += [_field(k, v) for k, v in p.fields.items() if v is not None]
            if not p.has_data:
                parts.append(tx["nodata"])
            if not p.csa_certified:
                parts.append(tx["csa"])
            lines.append(f"- {p.part_number}: " + ", ".join(parts))
        if len(products) > 5:
            lines.append(f"(+{len(products) - 5})")
        return "\n".join(lines)
    for r in reversed([t.result for t in trace if isinstance(t.result, dict)]):
        if r.get("status") == "no_match" and r.get("no_match"):
            return str(r["no_match"]["message"])
        if r.get("status") == "not_found":
            sug = ", ".join(r.get("suggestions") or [])
            return tx["notfound"] + (" " + tx["closest"].format(x=sug) if sug else "")
        if r.get("status") == "ambiguous":
            return tx["ambig"].format(x=", ".join(c["part_number"] for c in r["candidates"]))
    return tx["none"]


def build_result(
    answer: str, trace: list[ToolTrace], query: str, user_history: str = ""
) -> AgentResult:
    bad = unverified_numbers(answer, trace, query, user_history)
    bad += unverified_part_numbers(answer, trace, query, user_history)
    triggered = bool(bad)
    final = template_answer(trace, query) if triggered else answer
    out = list(trace)
    if triggered:
        params = {"unverified": bad, "original_answer": answer}
        out.append(ToolTrace(tool=GUARD_TOOL, params=params, result="template answer used"))
    return AgentResult(
        answer=final,
        products=products_from_trace(trace, final),
        trace=out,
        guard_triggered=triggered,
    )
