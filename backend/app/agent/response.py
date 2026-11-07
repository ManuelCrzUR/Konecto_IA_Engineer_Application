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
    The figures to verify in `text` (app/agent/numbers.py): digit tokens ('1,330',
    '2.3', '17', '2,3', as written) AND number words, English and Spanish 0..20
    ('seven', 'siete', 'diez', 'dieciseis'/'dieciséis'), after blanking every
    part-number-like token (regex r"76\\d[A-Z]\\d{2}(?:-[0-9A-Z]{8}(?:/A)?)?\\*?",
    case-insensitive) and the family name ("Series 76", "Serie 76", "Série 76").
    "one", "once", "un", "una", "uno" are not number words (articles/adverbs,
    too ambiguous). Only three kinds of number need no source (D-44):
    list ordinals (a number at the start of a line followed by "." or ")"),
    the 90 of a 90 degree stroke ("90°", "90 degrees", "90 grados"), and the
    tokens inside part numbers / the family name. There is no blanket 0..10 list.
- token_values(token) -> set[float]
    All readings of a token: '1,330' -> {1330.0, 1.33}; '2,3' -> {2.3};
    '1.330' -> {1.33, 1330.0}; '17' -> {17.0}; '1,234,567' -> {1234567.0}; 'siete' -> {7.0}.
- allowed_numbers(trace, query, user_history="") -> set[float]
    Every reading of every token found in: dict keys ('fla_50hz_a' -> 50) and all
    values (numbers and strings, recursively) of every trace result and params, the
    query, and `user_history` (what the USER typed in earlier turns; earlier
    assistant turns never count), plus the model size of each traced part number.
- unverified_numbers(answer, trace, query, user_history="", *, referent=None) -> list[str]
    Figures of the answer that fail the check. Product binding (D-44): for each
    figure, take the nearest PRECEDING part-number mention in the same sentence or
    line (a markdown table row is one line). If that part number matches a product
    in the trace (full part number or 6-char base), the figure must be one of the
    readings of THAT product's values (its actuator dict plus its table notes) or
    appear in the query / user_history; the same number on another product does not
    count. A figure with no such part number keeps the global rule (anywhere in the
    trace, query or user_history). `referent` (the product the conversation is
    about): when the answer mentions no part number at all, every figure is bound to
    the referent if it is in the trace; otherwise the global rule applies.
    Small talk (empty trace): every figure is unverified unless the user typed it.
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
- apply_persona(answer, model_id) -> (answer, replaced): rewrites the model's own
  display name (derived from its id) to Axel; pure.
- build_result(answer, trace, query, user_history="", model_id="", *, referent=None) -> AgentResult
    (`query` alone drives language detection; `user_history` is passed to the checks.)
    unverified = unverified_numbers(.., referent) + unverified_part_numbers.
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

from app.agent import numbers
from app.agent.numbers import PN_RE as _PN
from app.agent.numbers import token_values
from app.agent.tools import CSA_NOTE
from app.domain.conversation import AgentResult
from app.domain.models import Actuator, Product, ToolTrace

GUARD_TOOL = "number_guard"
EMPTY_TOOL = "empty_answer_guard"
PERSONA_TOOL = "persona_guard"
PERSONA_NAME = "Axel"
# Tokens of a model id that are not a distinctive name (so never rewritten).
_GENERIC_TOKENS = frozenset(
    {"free", "chat", "instruct", "preview", "beta", "latest", "turbo", "mini", "base",
     "online", "thinking", "exp", "experimental", "large", "small", "medium"}
)  # fmt: skip
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+|\n")
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
        "which": "Which product do you mean: {x}?",
    },
    "es": {
        "found": "Datos de las tablas:",
        "nodata": "figura en las tablas sin datos (N/A)",
        "csa": "sin certificación CSA",
        "notfound": "No encontré ese número de parte.",
        "closest": "Números de parte cercanos: {x}.",
        "ambig": "Coincide con varios números de parte: {x}. ¿Cuál necesitas?",
        "none": "No pude verificar una respuesta con los datos. ¿Puedes reformular la pregunta?",
        "which": "¿De cuál producto hablas: {x}?",
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


_COUNTED_LISTS = ("matches", "candidates", "suggestions")


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
        for raw, notes in items:
            if not isinstance(raw, dict) or "part_number" not in raw:
                continue
            pn = str(raw["part_number"]).upper().removesuffix("/A")
            vals = out.setdefault(pn, {float(pn[:3])})
            vals |= _readings(_walk(raw) + _walk(notes))
    return out


def _bound_values(by_pn: dict[str, set[float]], mention: str) -> set[float] | None:
    """Values of the traced products a part-number mention names (None: no such product)."""
    hits = [v for pn, v in by_pn.items() if pn.startswith(mention)]
    return set().union(*hits) if hits else None


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
    counts = _counts(trace)  # valid in any sentence, also next to a part number
    mentions = list(_PN.finditer(answer))
    starts = [0] + [m.end() for m in _SENTENCE_END.finditer(answer)]
    ref = (
        _bound_values(by_pn, _pn_tokens(referent)[0]) if referent and _pn_tokens(referent) else None
    )
    bad: list[str] = []
    for f in numbers.figures(answer):
        vals = token_values(f.token)
        if vals & user or vals & counts:
            continue
        seg = max(s for s in starts if s <= f.start)
        near = [m for m in mentions if m.start() >= seg and m.end() <= f.start]
        bound = _bound_values(by_pn, _pn_tokens(near[-1].group(0))[0]) if near else None
        if bound is None and not mentions:
            bound = ref
        if not vals & (allowed if bound is None else bound):
            bad.append(f.token)
    return bad


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


def template_answer(
    trace: list[ToolTrace], query: str, *, candidates: list[str] | None = None
) -> str:
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
    # A follow-up over several products shown before (D-47): ask which one, but only when
    # the turn did not go to the catalog or a search (then the question was about something else).
    if candidates and not any(t.tool in ("describe_catalog", "search_actuators") for t in trace):
        return tx["which"].format(x=", ".join(candidates))
    return tx["none"]


def _model_name_pattern(model_id: str) -> re.Pattern[str] | None:
    """Regex for the model's own display name, from its id ("vendor/crouton-alpha").

    Uses the last path segment, split on - _ space or dot. Tokens with digits
    (versions) and generic words are dropped. Needs a multi-token name, or one
    distinctive token of 4+ letters; otherwise None (nothing is rewritten).
    """
    segment = model_id.rsplit("/", 1)[-1].split(":")[0]
    tokens = [
        t for t in re.split(r"[-_ .]+", segment)
        if t.isalpha() and t.lower() not in _GENERIC_TOKENS
    ]  # fmt: skip
    if not tokens or (len(tokens) == 1 and len(tokens[0]) < 4):
        return None
    body = r"[-_ ]?".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def apply_persona(answer: str, model_id: str) -> tuple[str, list[str]]:
    """Replace the model's own name with Axel. Returns (answer, replaced terms)."""
    pattern = _model_name_pattern(model_id or "")
    if pattern is None:
        return answer, []
    found = [m.group(0) for m in pattern.finditer(answer)]
    return (pattern.sub(PERSONA_NAME, answer), found) if found else (answer, [])


def build_result(
    answer: str,
    trace: list[ToolTrace],
    query: str,
    user_history: str = "",
    model_id: str = "",
    *,
    referent: str | None = None,
    candidates: list[str] | None = None,
) -> AgentResult:
    out = list(trace)
    if not answer.strip():
        # An empty reply (e.g. a reasoning model that spent its token cap) never reaches the
        # user: the deterministic template answers from the trace instead.
        out.append(ToolTrace(tool=EMPTY_TOOL, params={}, result="template answer used"))
        final = template_answer(trace, query, candidates=candidates)
        return AgentResult(
            answer=final, products=products_from_trace(trace, final), trace=out,
            guard_triggered=True,
        )  # fmt: skip
    bad = unverified_numbers(answer, trace, query, user_history, referent=referent)
    bad += unverified_part_numbers(answer, trace, query, user_history)
    triggered = bool(bad)
    final = template_answer(trace, query, candidates=candidates) if triggered else answer
    if triggered:
        params = {"unverified": bad, "original_answer": answer}
        out.append(ToolTrace(tool=GUARD_TOOL, params=params, result="template answer used"))
    final, replaced = apply_persona(final, model_id)
    if replaced:
        result = f"model name replaced with {PERSONA_NAME}"
        out.append(ToolTrace(tool=PERSONA_TOOL, params={"replaced": replaced}, result=result))
    return AgentResult(
        answer=final,
        products=products_from_trace(trace, final),
        trace=out,
        guard_triggered=triggered,
    )
