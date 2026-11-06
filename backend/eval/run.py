"""Evaluation runner: runs eval/cases.yaml through run_agent and writes a report.

Usage (from backend/):
    uv run python -m eval.run                       # all cases, AGENT_MODEL from .env
    uv run python -m eval.run --only lookup-01,na-02 --workers 2
    uv run python -m eval.run --out eval/report.md

Case format (YAML list; see eval/cases.yaml):
  id: str (unique)            category: one of CATEGORIES
  turns: [str, ...]           (1 turn, or several for multi-turn; run in order,
                               history passed like the API would)
  expect:                     (all checks apply to the LAST turn's result)
    tools: [str]              each tool must appear in that turn's trace
    status: str               optional; status of the last trace result whose
                              tool is expect.tools[0] (found, found_no_data,
                              ambiguous, not_found, ok, no_match)
    products: [str]           part numbers that must ALL be in products
    no_products: bool         products must be empty
    answer_numbers: [str]     numbers (as strings, e.g. "1,330") that must
                              appear in the answer — matched by token_values,
                              so "1330" and "1,330" are equal
    out_of_catalog: bool      the last search result's no_match.out_of_catalog
    guard_ok: bool            default true: guard_triggered must be False

Contract:
- CATEGORIES = ("lookup", "recommend", "invalid_pn", "na", "impossible",
  "ambiguous", "out_of_subset", "multi_turn")
- load_cases(path) -> list[Case]  (pydantic, validates ids unique, category)
- run_case(case, *, llm, conn_factory) -> CaseResult
    runs every turn with app.agent.agent.run_agent (looked up at call time);
    builds history (HistoryTurn) between turns; catches exceptions into
    CaseResult.error. Records elapsed seconds, tools used, failures.
- check(case, result: AgentResult) -> list[str]   one message per failed check
- run_all(cases, *, llm_factory, conn_factory, workers=2) -> list[CaseResult]
    ThreadPoolExecutor; llm_factory() called per case (thread-safe models).
    Output order = input order.
- render_report(results, model_name) -> str  Markdown: summary (pass count,
  % by category), then a table id | category | pass | tools | seconds | failures.
- run_all(..., on_done=None): on_done(result) runs (serialized) after each
  completed case; if it raises BudgetExceeded no new case is scheduled and
  the partial results (completed cases, input order) are returned.
- main(argv=None) -> int: loads .env, ensure_data on the DB, runs, writes the
  report (default eval/report.md), prints the summary; exit 0 if pass rate
  >= --min-pass (default 0.9) else 1. --max-usd FLOAT wraps the run in
  app.spend.budgeted("eval", ...): usage is checked after each case; when the
  cap is exceeded the partial report is written and the exit code is 1.
"""

from __future__ import annotations

import argparse
import os
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from app.agent import agent as agent_mod
from app.domain.conversation import AgentResult, HistoryTurn
from app.spend import BudgetExceeded
from eval.cases import CATEGORIES, Case, CaseResult, Expect, check, load_cases

__all__ = ["CATEGORIES", "Case", "CaseResult", "Expect", "check", "load_cases",
           "main", "render_report", "run_all", "run_case"]  # fmt: skip

HERE = Path(__file__).parent


def run_case(case: Case, *, llm: Any, conn_factory: Any) -> CaseResult:
    start = time.perf_counter()
    history: list[HistoryTurn] = []
    tools: list[str] = []
    turns: list[tuple[str, str]] = []
    products: list[str] = []
    try:
        result: AgentResult | None = None
        for query in case.turns:
            result = agent_mod.run_agent(query, history, llm=llm, conn_factory=conn_factory)
            turns.append((query, result.answer))
            history = [
                *history,
                HistoryTurn(role="user", content=query),
                HistoryTurn(
                    role="assistant",
                    content=result.answer,
                    part_numbers=[p.part_number for p in result.products],
                ),
            ]
        assert result is not None
        tools = [t.tool for t in result.trace]
        products = [p.part_number for p in result.products]
        failures = check(case, result)
        error = None
    except Exception as exc:  # noqa: BLE001 - any failure is a failed case
        failures, error = [f"error: {type(exc).__name__}: {exc}"], str(exc) or type(exc).__name__
    elapsed = round(time.perf_counter() - start, 2)
    return CaseResult(
        id=case.id, category=case.category, passed=not failures, tools=tools,
        seconds=elapsed, failures=failures, error=error, turns=turns, products=products,
        expect=case.expect.model_dump(exclude_defaults=True),
    )  # fmt: skip


def run_all(
    cases: list[Case],
    *,
    llm_factory: Callable[[], Any],
    conn_factory: Any,
    workers: int = 2,
    on_done: Callable[[CaseResult], None] | None = None,
) -> list[CaseResult]:
    stop = threading.Event()
    lock = threading.Lock()

    def one(c: Case) -> CaseResult | None:
        if stop.is_set():
            return None
        try:
            llm = llm_factory()
        except Exception as exc:  # noqa: BLE001
            return CaseResult(id=c.id, category=c.category, passed=False,
                              failures=[f"error: {exc}"], error=str(exc))  # fmt: skip
        result = run_case(c, llm=llm, conn_factory=conn_factory)
        if on_done is not None:
            with lock:
                try:
                    on_done(result)
                except BudgetExceeded:
                    stop.set()
        return result

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return [r for r in pool.map(one, cases) if r is not None]


def render_report(results: list[CaseResult], model_name: str) -> str:
    ok = sum(r.passed for r in results)
    lines = [f"# Evaluation report\n\nModel: `{model_name}`\n",
             f"Passed: {ok}/{len(results)} ({ok / max(len(results), 1):.0%})\n",
             "| category | passed | % |", "|---|---|---|"]  # fmt: skip
    for cat in dict.fromkeys(r.category for r in results):
        sub = [r for r in results if r.category == cat]
        n = sum(r.passed for r in sub)
        lines.append(f"| {cat} | {n}/{len(sub)} | {n / len(sub):.0%} |")
    lines += [
        "",
        "| id | category | pass | tools | seconds | failures |",
        "|---|---|---|---|---|---|",
    ]
    for r in results:
        fails = "; ".join(r.failures).replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {r.id} | {r.category} | {'PASS' if r.passed else 'FAIL'} | "
            f"{', '.join(r.tools)} | {r.seconds} | {fails} |"
        )
    lines += ["", "## Transcripts", ""]
    for r in results:
        lines.append(f"### {r.id} ({r.category}): {'PASS' if r.passed else 'FAIL'}\n")
        for q, a in r.turns:
            lines += [
                f"**User:** {q}\n",
                "**Assistant:**\n",
                *(f"> {x}" for x in a.splitlines()),
                "",
            ]
        lines.append(f"- Expected: `{r.expect}`")
        lines.append(
            f"- Tools: {', '.join(r.tools) or '-'}; products: {', '.join(r.products) or '-'}"
        )
        if r.failures:
            lines.append(f"- Failures: {'; '.join(r.failures)}")
        lines.append("")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the agent evaluation set")
    ap.add_argument("--only", default="", help="comma-separated case ids")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", type=Path, default=HERE / "report.md")
    ap.add_argument("--min-pass", type=float, default=0.9)
    ap.add_argument("--max-usd", type=float, default=None,
                    help="abort when the eval spends more than this (OpenRouter key usage)")  # fmt: skip
    ap.add_argument("--cases", type=Path, default=HERE / "cases.yaml")
    args = ap.parse_args(argv)

    load_dotenv()
    from app.bootstrap import ensure_data
    from app.db.connection import conn_factory, connect
    from app.llm import get_llm

    cases = load_cases(args.cases)
    if args.only:
        wanted = {s.strip() for s in args.only.split(",") if s.strip()}
        unknown = wanted - {c.id for c in cases}
        if unknown:
            ap.error(f"unknown case ids: {sorted(unknown)}")
        cases = [c for c in cases if c.id in wanted]
    with connect() as conn:
        ensure_data(conn)  # no escalator: never spends LLM budget here
    model = os.environ.get("AGENT_MODEL", "unknown")
    aborted = False
    if args.max_usd is None:
        results = run_all(cases, llm_factory=lambda: get_llm("agent"),
                          conn_factory=conn_factory(), workers=args.workers)  # fmt: skip
    else:
        from app.spend import SpendError, budgeted

        results = []
        try:
            with budgeted("eval", args.max_usd, model=model) as budget:
                over: list[BudgetExceeded] = []

                def on_done(r: CaseResult) -> None:
                    budget.calls += 1
                    try:
                        budget.check()
                    except BudgetExceeded as exc:
                        over.append(exc)
                        raise

                results = run_all(cases, llm_factory=lambda: get_llm("agent"),
                                  conn_factory=conn_factory(), workers=args.workers,
                                  on_done=on_done)  # fmt: skip
                if over:
                    raise over[0]  # logged as "aborted"
        except BudgetExceeded as exc:
            aborted = True
            print(f"Budget cap exceeded: {exc}")
        except SpendError as exc:
            print(f"Spend control: {exc}")
            return 2
    report = render_report(results, model)
    args.out.write_text(report)
    rate = sum(r.passed for r in results) / max(len(results), 1)
    print(report.split("| id |")[0])
    print(f"Report written to {args.out}")
    if aborted:
        print(f"Stopped after {len(results)}/{len(cases)} cases")
        return 1
    return 0 if rate >= args.min_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
