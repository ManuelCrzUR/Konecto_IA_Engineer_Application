"""LangChain tools: thin wrappers over db/actuators_repo. No LLM knowledge here.

Contract (pure functions take an open psycopg connection; they never commit):

- normalize_part_number(text) -> str
    Uppercase; drop all whitespace and '*'. If the result is a full part number
    without its dash (e.g. '764A0011300000'), insert the dash after 6 chars.
    If it is a full part number without '/A', append '/A'. A dashless partial
    longer than the 6-char base gets its dash too ('761A001130' -> '761A00-1130').
    Anything else (a base like '764A00', a fragment like '764') is returned
    as is (uppercased, cleaned). Never raises.
      ' 764a00-11300000/a ' -> '764A00-11300000/A'
      '764A00-11300000'     -> '764A00-11300000/A'
      '766A00-11320000/A*'  -> '766A00-11320000/A'
      '764a'                -> '764A'

- lookup_actuator(conn, part_number) -> ActuatorLookup
    1. Exact match on the normalized PN -> 'found' (has_data) or
       'found_no_data' (N/A row). `actuator` set; `notes` = table notes
       (actuators_repo.table_notes) + the CSA note when csa_certified is False.
    2. Else prefix match (actuators_repo.find_like, normalized input, at most
       20 rows; empty input or input shorter than 3 chars skips this step):
       exactly one row -> treated as step 1; several -> 'ambiguous' with
       `candidates` (Candidate per row, ordered by part_number).
    3. Else 'not_found' with up to 5 `suggestions`: the closest catalog PNs by
       difflib similarity to the normalized input (empty if none is close,
       cutoff 0.5). Inputs not shaped like a Series 76 PN still get this result.

- search(conn, filters, limit=5) -> SearchResult
    actuators_repo.search + count_matches. Empty -> status 'no_match' with
    `no_match` = actuators_repo.diagnose_no_match. `filters` echoes the input.

- describe(conn) -> CatalogSummary: actuators_repo.catalog_summary.

- make_tools(conn_factory) -> list[BaseTool], named as TOOL_NAMES, in order:
    get_actuator(part_number: str)
    search_actuators(<SearchFilters fields, flat>)   args_schema = SearchFilters
    describe_catalog()
  Each opens a connection with `with conn_factory() as conn:`, calls the pure
  function and returns `as_printed(result.model_dump(mode="json"))` (a dict:
  whole-number floats become ints, 750.0 -> 750, as the PDF prints them). Tool
  descriptions tell the LLM when to use each tool; they contain no numbers
  from the catalog. Errors from the DB propagate (the agent layer handles them).
  The LLM never writes SQL.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

import psycopg
from langchain_core.tools import BaseTool, StructuredTool

from app.db import actuators_repo as repo
from app.db.connection import ConnFactory
from app.domain.models import Actuator
from app.domain.search import (
    ActuatorLookup,
    Candidate,
    CatalogSummary,
    SearchFilters,
    SearchResult,
)

TOOL_NAMES = ("get_actuator", "search_actuators", "describe_catalog")
CSA_NOTE = "Sizes 6 and 7 are not CSA Certified"
_FULL_PN = re.compile(r"^(76\d[A-Z]\d{2})-?([0-9A-Z]{8})(?:/A)?$")
_PARTIAL_NO_DASH = re.compile(r"^(76\d[A-Z]\d{2})([0-9A-Z]{1,7})$")
_MIN_PREFIX = 3
_MAX_PREFIX_ROWS = 20
_MAX_SUGGESTIONS = 5
_CUTOFF = 0.5


def normalize_part_number(text: str) -> str:
    cleaned = re.sub(r"[\s*]+", "", text).upper()
    m = _FULL_PN.match(cleaned)
    if m:
        return f"{m.group(1)}-{m.group(2)}/A"
    p = _PARTIAL_NO_DASH.match(cleaned)  # '761A001130' -> '761A00-1130' for prefix search
    return f"{p.group(1)}-{p.group(2)}" if p else cleaned


def _found(conn: psycopg.Connection, query: str, norm: str, a: Actuator) -> ActuatorLookup:
    notes = repo.table_notes(conn, [a.table_id]).get(a.table_id, [])
    if not a.csa_certified:
        notes = [*notes, CSA_NOTE]
    return ActuatorLookup(
        status="found" if a.has_data else "found_no_data",
        query=query,
        normalized=norm,
        actuator=a,
        notes=notes,
    )


def _suggest(conn: psycopg.Connection, norm: str) -> list[str]:
    """Closest catalog PNs by difflib ratio against the full PN or its base (before '-')."""
    scored = []
    for a in repo.find_like(conn, "", limit=repo.count(conn)):
        pn = a.part_number
        score = max(
            SequenceMatcher(None, norm, pn).ratio(),
            SequenceMatcher(None, norm, pn.split("-")[0]).ratio(),
        )
        if score >= _CUTOFF:
            scored.append((-score, pn))
    return [pn for _, pn in sorted(scored)[:_MAX_SUGGESTIONS]]


def lookup_actuator(conn: psycopg.Connection, part_number: str) -> ActuatorLookup:
    norm = normalize_part_number(part_number)
    exact = repo.get_by_pn(conn, norm) if norm else None
    if exact:
        return _found(conn, part_number, norm, exact)
    if len(norm) >= _MIN_PREFIX:
        rows = repo.find_like(conn, norm, limit=_MAX_PREFIX_ROWS)
        if len(rows) == 1:
            return _found(conn, part_number, norm, rows[0])
        if rows:
            cands = [
                Candidate(
                    part_number=r.part_number,
                    enclosure=r.enclosure,
                    voltage=r.voltage,
                    phase=r.phase,
                    service=r.service,
                    has_data=r.has_data,
                )
                for r in rows
            ]
            return ActuatorLookup(
                status="ambiguous", query=part_number, normalized=norm, candidates=cands
            )
    return ActuatorLookup(
        status="not_found",
        query=part_number,
        normalized=norm,
        suggestions=_suggest(conn, norm),
    )


def search(conn: psycopg.Connection, filters: SearchFilters, limit: int = 5) -> SearchResult:
    matches = repo.search(conn, filters, limit=limit)
    if not matches:
        report = repo.diagnose_no_match(conn, filters)
        return SearchResult(status="no_match", filters=filters, no_match=report)
    return SearchResult(
        status="ok",
        filters=filters,
        matches=matches,
        total=repo.count_matches(conn, filters),
    )


def describe(conn: psycopg.Connection) -> CatalogSummary:
    return repo.catalog_summary(conn)


def as_printed(obj: Any) -> Any:
    """Whole-number floats -> int, recursively (750.0 -> 750; 1.1 stays). Not a
    conversion: the value is identical, only the LLM-facing spelling changes."""
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    if isinstance(obj, dict):
        return {k: as_printed(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [as_printed(v) for v in obj]
    return obj


def make_tools(conn_factory: ConnFactory) -> list[BaseTool]:
    def get_actuator(part_number: str) -> dict:
        with conn_factory() as conn:
            return as_printed(lookup_actuator(conn, part_number).model_dump(mode="json"))

    def search_actuators(**kwargs: object) -> dict:
        with conn_factory() as conn:
            return as_printed(search(conn, SearchFilters(**kwargs)).model_dump(mode="json"))  # type: ignore[arg-type]

    def describe_catalog() -> dict:
        with conn_factory() as conn:
            return as_printed(describe(conn).model_dump(mode="json"))

    return [
        StructuredTool.from_function(
            get_actuator,
            name="get_actuator",
            description=(
                "Look up ONE Series 76 actuator by part number (any case, with or without "
                "dash, '/A' or '*'). Use whenever the user names a part number or a fragment "
                "of one. Returns status found, found_no_data (valid part number printed as "
                "N/A), ambiguous (several candidates: ask the user which one) or not_found "
                "(with close suggestions). Quote numbers only from the result."
            ),
        ),
        StructuredTool.from_function(
            search_actuators,
            name="search_actuators",
            description=(
                "Find actuators that meet technical requirements (minimum torque with its "
                "unit, voltage, phase, enclosure, service, maximum speed, minimum duty "
                "cycle). Use for recommendations when no part number is given. Set only the "
                "fields the user stated. Returns the tightest-fitting matches first, or "
                "no_match with the blocking requirement and the closest available value. "
                "Quote numbers only from the result."
            ),
            args_schema=SearchFilters,
        ),
        StructuredTool.from_function(
            describe_catalog,
            name="describe_catalog",
            description=(
                "Summarize what the catalog contains (voltages, phases, enclosures, "
                "services, torque ranges, row counts). Use for vague or broad questions, "
                "or to check whether a combination exists before answering 'no data'."
            ),
        ),
    ]
