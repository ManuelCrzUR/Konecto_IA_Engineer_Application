"""Deterministic fallback answer, built only from the tool trace. Pure code.

Input:  `trace`, `query` (its language is detected) and optional `candidates`
        (products shown in the previous turn, D-47).
Output: template_answer(trace, query, candidates=None) -> str, detect_lang(query) -> "es" | "en".

Contract:
- template_answer uses the products (part number, voltage, enclosure and the printed
  fields with their units), else the last no_match message / not found suggestions /
  ambiguous candidates, else a "which product do you mean" line (only when the turn
  did not call describe_catalog or search_actuators), else a short "could not verify,
  please rephrase" line. Every number in it comes from the trace.
- detect_lang: cheap heuristic: Spanish accents/inverted marks or common Spanish
  words -> "es".
"""

from __future__ import annotations

import re
from typing import Literal

from app.agent.products import products_from_trace
from app.domain.models import ToolTrace

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
