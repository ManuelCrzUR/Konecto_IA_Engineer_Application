"""Eval case format and checks (no I/O besides reading the YAML, no LLM).

Case/Expect describe one case of eval/cases.yaml (format in eval/run.py's
docstring); check(case, result) returns one message per failed expectation;
CaseResult is what the runner records per case.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

from app.agent.response import extract_numbers, token_values
from app.domain.conversation import AgentResult

CATEGORIES = (
    "lookup", "recommend", "invalid_pn", "na", "impossible",
    "ambiguous", "out_of_subset", "multi_turn",
)  # fmt: skip


class Expect(BaseModel):
    tools: list[str] = Field(default_factory=list)
    status: str | None = None
    products: list[str] = Field(default_factory=list)
    no_products: bool = False
    answer_numbers: list[str] = Field(default_factory=list)
    out_of_catalog: bool | None = None
    guard_ok: bool = True


class Case(BaseModel):
    id: str
    category: str
    turns: list[str] = Field(min_length=1)
    expect: Expect = Field(default_factory=Expect)

    @field_validator("category")
    @classmethod
    def _category(cls, v: str) -> str:
        if v not in CATEGORIES:
            raise ValueError(f"unknown category {v!r}; expected one of {CATEGORIES}")
        return v


class CaseResult(BaseModel):
    id: str
    category: str
    passed: bool
    tools: list[str] = Field(default_factory=list)
    seconds: float = 0.0
    failures: list[str] = Field(default_factory=list)
    error: str | None = None
    turns: list[tuple[str, str]] = Field(default_factory=list)  # (question, answer)
    products: list[str] = Field(default_factory=list)
    expect: dict[str, Any] = Field(default_factory=dict)


class _CaseList(BaseModel):
    cases: list[Case]

    @model_validator(mode="after")
    def _unique(self) -> _CaseList:
        ids = [c.id for c in self.cases]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"duplicate case ids: {dup}")
        return self


def load_cases(path: Path | str) -> list[Case]:
    raw = yaml.safe_load(Path(path).read_text()) or []
    return _CaseList(cases=raw).cases


def _last_result(result: AgentResult, tool: str) -> Any:
    hits = [t.result for t in result.trace if t.tool == tool]
    return hits[-1] if hits else None


def _field(res: Any, key: str) -> Any:
    return res.get(key) if isinstance(res, dict) else None


def check(case: Case, result: AgentResult) -> list[str]:
    e, bad = case.expect, []
    used = [t.tool for t in result.trace]
    for tool in e.tools:
        if tool not in used:
            bad.append(f"tool {tool} not called (called: {used})")
    if e.status is not None and e.tools:
        got = _field(_last_result(result, e.tools[0]), "status")
        if got != e.status:
            bad.append(f"status of {e.tools[0]}: expected {e.status}, got {got}")
    shown = {p.part_number for p in result.products}
    missing = [p for p in e.products if p not in shown]
    if missing:
        bad.append(f"products missing: {missing} (shown: {sorted(shown)})")
    if e.no_products and shown:
        bad.append(f"expected no products, got {sorted(shown)}")
    if e.answer_numbers:
        have: set[float] = set()
        for tok in extract_numbers(result.answer):
            have |= token_values(tok)
        bad += [f"number {n} not in answer" for n in e.answer_numbers if not token_values(n) & have]
    if e.out_of_catalog is not None:
        nm = _field(_last_result(result, "search_actuators"), "no_match")
        got = _field(nm, "out_of_catalog")
        if bool(got) != e.out_of_catalog:
            bad.append(f"out_of_catalog: expected {e.out_of_catalog}, got {got}")
    if e.guard_ok and result.guard_triggered:
        bad.append("guard_triggered (answer had unverified numbers)")
    return bad
